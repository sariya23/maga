import math
from datetime import datetime, timedelta, timezone

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.models import Portfolio
from valutatrade_hub.infra.database import JsonStorage
from valutatrade_hub.infra.settings import SettingsLoader


def validate_currency(value: str) -> str:
    return get_currency(value).code


def validate_amount(value: float) -> float:
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
    """Курсы: свежий кеш, обратная/кросс-пара или учебная заглушка."""

    def __init__(self, storage: JsonStorage) -> None:
        self.storage = storage
        self.exchange_rates = Portfolio.exchange_rates.copy()
        self.settings = SettingsLoader()

    @property
    def ttl(self) -> timedelta:
        return timedelta(seconds=self.settings.get("RATES_TTL_SECONDS"))

    def _fetch_usd_rate(self, code: str) -> float:
        """Точка подключения Parser Service вместо учебной заглушки."""
        try:
            return validate_amount(self.exchange_rates[code])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiRequestError(f"нет данных для {code}→USD") from exc

    @staticmethod
    def _timestamp(value: str) -> datetime:
        timestamp = datetime.fromisoformat(value)
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
        with self.storage.transaction("rates") as documents:
            result = self._resolve_rate(documents["rates"], source, target, now)
        return {"from_currency": source, "to_currency": target, **result}

    def _resolve_rate(
        self, cache: dict, source: str, target: str, now: datetime
    ) -> dict:
        result = self._cached_pair(cache, source, target, now)
        if result is None:
            legs = []
            refreshed = False
            for code in (source, target):
                leg = self._cached_pair(cache, code, "USD", now)
                if leg is None:
                    try:
                        fetched_rate = validate_amount(self._fetch_usd_rate(code))
                    except ApiRequestError:
                        raise
                    except (OSError, ValueError, TypeError) as exc:
                        raise ApiRequestError(str(exc)) from exc
                    leg = {
                        "rate": fetched_rate,
                        "updated_at": now.isoformat(),
                    }
                    cache[f"{code}_USD"] = leg
                    refreshed = True
                legs.append(leg)
            rate = legs[0]["rate"] / legs[1]["rate"]
            if not math.isfinite(rate) or rate <= 0:
                raise ApiRequestError(f"некорректный курс {source}→{target}")
            result = {
                "rate": rate,
                "updated_at": min(leg["updated_at"] for leg in legs),
            }
            if refreshed:
                cache["source"] = "StubRateService"
                cache["last_refresh"] = now.isoformat()
        return result
