from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import validate_amount
from valutatrade_hub.parser_service.config import ParserConfig


def utc_timestamp(value: datetime | None = None) -> str:
    return (
        (value or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class BaseApiClient(ABC):
    source = ""

    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        self.metadata: dict[str, dict] = {}

    def _request(self, url: str, params: dict | None = None) -> tuple[dict, dict]:
        self.metadata = {}
        start = perf_counter()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
            if response.status_code != 200:
                reason = (
                    "лимит запросов превышен"
                    if response.status_code == 429
                    else "запрос отклонён"
                )
                raise ApiRequestError(
                    f"{self.source}: HTTP {response.status_code}, {reason}"
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("expected object")
        except requests.exceptions.RequestException:
            # requests exceptions may contain the URL with the API key.
            raise ApiRequestError(f"{self.source}: ошибка сети или таймаут") from None
        except ApiRequestError:
            raise
        except (ValueError, TypeError):
            raise ApiRequestError(f"{self.source}: некорректный JSON-ответ") from None
        meta = {
            "request_ms": round((perf_counter() - start) * 1000),
            "status_code": 200,
        }
        if response.headers.get("ETag"):
            meta["etag"] = response.headers["ETag"]
        return payload, meta

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Return pair -> rate; per-pair timestamp and meta are in metadata."""


class CoinGeckoClient(BaseApiClient):
    source = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        config = self.config
        try:
            ids = [config.CRYPTO_ID_MAP[code] for code in config.CRYPTO_CURRENCIES]
            payload, meta = self._request(
                config.COINGECKO_URL,
                {
                    "ids": ",".join(ids),
                    "vs_currencies": config.BASE_CURRENCY.lower(),
                    "include_last_updated_at": "true",
                },
            )
            rates = {}
            received = utc_timestamp()
            for code, raw_id in zip(config.CRYPTO_CURRENCIES, ids):
                row = payload[raw_id]
                pair = f"{code}_{config.BASE_CURRENCY}"
                rates[pair] = validate_amount(row[config.BASE_CURRENCY.lower()])
                timestamp = received
                if "last_updated_at" in row:
                    timestamp = utc_timestamp(
                        datetime.fromtimestamp(
                            validate_amount(row["last_updated_at"]), timezone.utc
                        )
                    )
                self.metadata[pair] = {
                    "timestamp": timestamp,
                    "meta": {**meta, "raw_id": raw_id},
                }
            return rates
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            if isinstance(exc, ApiRequestError):
                raise
            raise ApiRequestError(f"{self.source}: неверный формат котировок") from None


class ExchangeRateApiClient(BaseApiClient):
    source = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        config = self.config
        if not config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                "ExchangeRate-API: задайте EXCHANGERATE_API_KEY в .env"
            )
        payload, meta = self._request(
            f"{config.EXCHANGERATE_API_URL}/{config.EXCHANGERATE_API_KEY}/latest/{config.BASE_CURRENCY}"
        )
        if payload.get("result") != "success":
            reasons = {
                "invalid-key": "неверный ключ",
                "inactive-account": "аккаунт не активирован",
                "quota-reached": "лимит запросов превышен",
            }
            raise ApiRequestError(
                f"{self.source}: {reasons.get(payload.get('error-type'), 'API отклонил запрос')}"
            )
        try:
            if payload["base_code"] != config.BASE_CURRENCY:
                raise ValueError("unexpected base")
            values = payload.get("conversion_rates", payload.get("rates"))
            if "time_last_update_unix" in payload:
                timestamp = utc_timestamp(
                    datetime.fromtimestamp(
                        validate_amount(payload["time_last_update_unix"]), timezone.utc
                    )
                )
            else:
                timestamp = utc_timestamp(
                    parsedate_to_datetime(payload["time_last_update_utc"])
                )
            rates = {}
            for code in config.FIAT_CURRENCIES:
                pair = f"{code}_{config.BASE_CURRENCY}"
                rates[pair] = validate_amount(1 / validate_amount(values[code]))
                self.metadata[pair] = {"timestamp": timestamp, "meta": dict(meta)}
            return rates
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            raise ApiRequestError(f"{self.source}: неверный формат котировок") from None
