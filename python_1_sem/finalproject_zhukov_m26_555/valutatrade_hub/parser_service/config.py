from dataclasses import dataclass, field

from valutatrade_hub.core.constants import REFERENCE_CURRENCY


@dataclass
class ParserConfig:
    # Environment is read only in main(); secrets are passed explicitly.
    """Параметры API и файлов; секрет передаётся из main явно."""

    EXCHANGERATE_API_KEY: str | None = field(default=None, repr=False)
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    BASE_CURRENCY: str = REFERENCE_CURRENCY
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"
    REQUEST_TIMEOUT: float = 10
    UPDATE_INTERVAL: float = 3600
