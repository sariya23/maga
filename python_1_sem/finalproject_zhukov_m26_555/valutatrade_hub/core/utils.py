import math
from datetime import datetime, timedelta, timezone

from valutatrade_hub.core.constants import REFERENCE_CURRENCY
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.database import JsonStorage
from valutatrade_hub.infra.settings import SettingsLoader


def validate_currency(value: str) -> str:
    """Нормализовать код и проверить наличие валюты в реестре."""
    return get_currency(value).code


def validate_amount(value: float) -> float:
    """Вернуть положительное конечное число, отклонив bool и строки."""
    message = "'amount' должен быть положительным числом"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(message)
    try:
        amount = float(value)
    except OverflowError:
        raise ValueError(message) from None
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError(message)
    return amount


class RateService:
    """Прямые, обратные и кросс-курсы только из свежего локального кеша."""

    def __init__(self, storage: JsonStorage) -> None:
        self.storage = storage
        self.settings = SettingsLoader()

    @property
    def ttl(self) -> timedelta:
        """Вернуть актуальный срок годности котировки из настроек."""
        return timedelta(seconds=self.settings.get("RATES_TTL_SECONDS"))

    @staticmethod
    def _timestamp(value: str) -> datetime:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Для старого кеша без часового пояса считаем время UTC.
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    def _cached_pair(self, cache: dict, source: str, target: str, now: datetime):
        if source == target:
            return {"rate": 1.0, "updated_at": now.isoformat()}
        for key, inverse in (
            (f"{source}_{target}", False),
            (f"{target}_{source}", True),
        ):
            entry = cache.get(key)
            if not isinstance(entry, dict):
                continue
            try:
                rate = validate_amount(entry["rate"])
                updated_at = self._timestamp(entry["updated_at"])
                if not timedelta(0) <= now - updated_at < self.ttl:
                    continue
                rate = validate_amount(1 / rate if inverse else rate)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            return {"rate": rate, "updated_at": updated_at.isoformat()}
        return None

    def get_rate(self, from_currency: str, to_currency: str) -> dict:
        """Вернуть from_currency, to_currency, rate, updated_at (ISO, UTC)."""
        source = validate_currency(from_currency)
        target = validate_currency(to_currency)
        now = datetime.now(timezone.utc)
        document = self.storage.read("rates")
        cache = document.get("pairs", {})
        if not isinstance(cache, dict):
            raise ApiRequestError("неверный формат кеша; выполните update-rates")
        result = self._resolve_rate(cache, source, target, now)
        return {"from_currency": source, "to_currency": target, **result}

    def _resolve_rate(
        self, cache: dict, source: str, target: str, now: datetime
    ) -> dict:
        result = self._cached_pair(cache, source, target, now)
        if result is not None:
            return result
        legs = [
            self._cached_pair(cache, code, REFERENCE_CURRENCY, now)
            for code in (source, target)
        ]
        if any(leg is None for leg in legs):
            raise ApiRequestError(
                f"курс {source}→{target} отсутствует или устарел; выполните update-rates"
            )
        return {
            "rate": validate_amount(legs[0]["rate"] / legs[1]["rate"]),
            "updated_at": min(leg["updated_at"] for leg in legs),
        }
