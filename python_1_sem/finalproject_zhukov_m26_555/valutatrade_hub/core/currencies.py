import math
import re
from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


def normalize_code(code: str) -> str:
    if not isinstance(code, str):
        raise TypeError("Код валюты должен быть строкой")
    normalized = code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,5}", normalized):
        raise ValueError("Код валюты: 2–5 латинских букв или цифр без пробелов")
    return normalized


def _nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} не может быть пустым")
    return value.strip()


class Currency(ABC):
    """Общий контракт валюты: имя, код и представление для UI/логов."""

    def __init__(self, name: str, code: str) -> None:
        self.name = name
        self.code = code

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = _nonempty(value, "Название валюты")

    @property
    def code(self) -> str:
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        normalized = normalize_code(value)
        if normalized != value:
            raise ValueError("Код валюты должен быть в верхнем регистре без пробелов")
        self._code = normalized

    @abstractmethod
    def get_display_info(self) -> str:
        """Вернуть описание с типом валюты и её специфическими атрибутами."""


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        self.issuing_country = _nonempty(issuing_country, "Страна эмиссии")

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name, code)
        self.algorithm = _nonempty(algorithm, "Алгоритм")
        if isinstance(market_cap, bool) or not isinstance(market_cap, (int, float)):
            raise TypeError("Капитализация должна быть числом")
        try:
            market_cap = float(market_cap)
        except OverflowError:
            raise ValueError("Капитализация слишком велика") from None
        if not math.isfinite(market_cap) or market_cap < 0:
            raise ValueError("Капитализация должна быть конечной и неотрицательной")
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        mantissa, exponent = f"{self.market_cap:.2e}".split("e")
        cap = f"{mantissa.rstrip('0').rstrip('.')}e{int(exponent)}"
        return (
            f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {cap})"
        )


# Капитализация в реестре — учебные данные, а не текущая котировка API.
_CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "SOL": CryptoCurrency("Solana", "SOL", "PoS / PoH", 0),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
}


def get_currency(code: str) -> Currency:
    normalized = normalize_code(code)
    try:
        return _CURRENCIES[normalized]
    except KeyError:
        raise CurrencyNotFoundError(normalized) from None


def supported_codes() -> tuple[str, ...]:
    return tuple(sorted(_CURRENCIES))
