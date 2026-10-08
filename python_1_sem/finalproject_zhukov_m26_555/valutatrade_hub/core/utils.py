import json
import math
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from valutatrade_hub.core.models import Portfolio

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def validate_currency(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Код валюты должен быть непустой строкой")
    code = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]*", code):
        raise ValueError("Код валюты должен содержать латинские буквы и цифры")
    return code


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


class StorageError(ValueError):
    pass


class JsonStorage:
    def __init__(self, data_dir: str | Path = DEFAULT_DATA_DIR) -> None:
        self.data_dir = Path(data_dir)

    def read(self, name: str) -> list | dict:
        path = self.data_dir / f"{name}.json"
        expected_type = dict if name == "rates" else list
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return expected_type()
        if not text.strip():
            return expected_type()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StorageError(f"Повреждён файл {path.name}: {exc.msg}") from exc
        if not isinstance(data, expected_type):
            raise StorageError(f"Неверный формат файла {path.name}")
        return data

    def write(self, name: str, data: list | dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.data_dir, delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(text)
            os.replace(temporary_path, self.data_dir / f"{name}.json")
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


class RateUnavailableError(ValueError):
    pass


class RateService:
    """Курсы: свежий кеш, обратная/кросс-пара или учебная заглушка."""

    def __init__(self, storage: JsonStorage) -> None:
        self.storage = storage
        self.exchange_rates = Portfolio.exchange_rates.copy()
        self.ttl = timedelta(minutes=5)

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
        for key, inverse in ((f"{source}_{target}", False),
                             (f"{target}_{source}", True)):
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
        cache = self.storage.read("rates")
        if source == target and source not in self.exchange_rates:
            known = any(
                source in key.split("_")
                and len(key.split("_")) == 2
                and self._cached_pair(cache, *key.split("_"), now)
                for key in cache
            )
            if not known:
                raise RateUnavailableError(
                    f"Курс {source}→{target} недоступен. Повторите попытку позже."
                )
        result = self._cached_pair(cache, source, target, now)
        if result is None:
            legs = []
            refreshed = False
            for code in (source, target):
                leg = self._cached_pair(cache, code, "USD", now)
                if leg is None:
                    if code not in self.exchange_rates:
                        raise RateUnavailableError(
                            f"Курс {source}→{target} недоступен. Повторите попытку позже."
                        )
                    leg = {
                        "rate": self.exchange_rates[code],
                        "updated_at": now.isoformat(),
                    }
                    cache[f"{code}_USD"] = leg
                    refreshed = True
                legs.append(leg)
            rate = legs[0]["rate"] / legs[1]["rate"]
            if not math.isfinite(rate) or rate <= 0:
                raise RateUnavailableError(f"Курс {source}→{target} недоступен")
            result = {
                "rate": rate,
                "updated_at": min(leg["updated_at"] for leg in legs),
            }
            if refreshed:
                cache["source"] = "StubRateService"
                cache["last_refresh"] = now.isoformat()
                self.storage.write("rates", cache)
        return {"from_currency": source, "to_currency": target, **result}
