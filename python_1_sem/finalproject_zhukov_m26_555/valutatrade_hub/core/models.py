import hashlib
import hmac
import math
from collections.abc import Callable
from datetime import datetime

from valutatrade_hub.core.constants import REFERENCE_CURRENCY
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
)


class User:
    """Пользователь с солёным хешем пароля и датой регистрации."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("Идентификатор должен быть положительным целым числом")
        if not isinstance(hashed_password, str) or not hashed_password:
            raise ValueError("Хеш пароля не может быть пустым")
        if not isinstance(salt, str) or not salt:
            raise ValueError("Соль не может быть пустой")
        if not isinstance(registration_date, datetime):
            raise TypeError("Дата регистрации должна иметь тип datetime")

        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        """Вернуть неизменяемый идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Получить или установить непустое имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Получить или установить непустое имя пользователя."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Вернуть хеш пароля для сериализации."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Вернуть индивидуальную соль для сериализации."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Вернуть дату регистрации пользователя."""
        return self._registration_date

    def get_user_info(self) -> dict[str, int | str]:
        """Вернуть публичные данные без хеша пароля и соли."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Проверить длину пароля и заменить его SHA-256 хеш."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        self._hashed_password = self._hash_password(new_password)

    def verify_password(self, password: str) -> bool:
        """Сравнить хеш переданного пароля с сохранённым."""
        if not isinstance(password, str):
            raise TypeError("Пароль должен быть строкой")
        return hmac.compare_digest(
            self._hash_password(password).encode("utf-8"),
            self.hashed_password.encode("utf-8"),
        )

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256((password + self.salt).encode("utf-8")).hexdigest()


class Wallet:
    """Кошелёк одной валюты с конечным неотрицательным балансом."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self._currency_code = get_currency(currency_code).code
        self.balance = balance

    @property
    def currency_code(self) -> str:
        """Вернуть код валюты кошелька."""
        return self._currency_code

    @property
    def balance(self) -> float:
        """Получить или установить конечный неотрицательный баланс."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Получить или установить конечный неотрицательный баланс."""
        value = self._validate_number(value)
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = value

    def deposit(self, amount: float) -> None:
        """Пополнить кошелёк на положительную конечную сумму."""
        amount = self._validate_amount(amount)
        self.balance = self.balance + amount

    def withdraw(self, amount: float) -> None:
        """Списать сумму или выбросить InsufficientFundsError."""
        amount = self._validate_amount(amount)
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount, self.currency_code)
        self.balance = self.balance - amount

    def get_balance_info(self) -> dict[str, str | float]:
        """Вернуть код валюты и текущий баланс."""
        return {"currency_code": self.currency_code, "balance": self.balance}

    @staticmethod
    def _validate_number(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Значение должно быть числом")
        try:
            number = float(value)
        except OverflowError:
            raise ValueError("Значение должно быть конечным числом") from None
        if not math.isfinite(number):
            raise ValueError("Значение должно быть конечным числом")
        return number

    @classmethod
    def _validate_amount(cls, amount: float) -> float:
        amount = cls._validate_number(amount)
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
        return amount


class Portfolio:
    """Кошельки пользователя и оценка через поставщика актуальных курсов."""

    def __init__(
        self,
        user_id: int,
        user: User,
        wallets: dict[str, Wallet] | None = None,
        rate_provider: Callable[[str, str], dict] | None = None,
    ) -> None:
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("Идентификатор должен быть положительным целым числом")
        if not isinstance(user, User):
            raise TypeError("Пользователь должен быть объектом User")
        if user.user_id != user_id:
            raise ValueError("Идентификатор портфеля не совпадает с пользователем")
        if wallets is not None and not isinstance(wallets, dict):
            raise TypeError("Кошельки должны быть словарём")

        self._user_id = user_id
        self._user = user
        self._rate_provider = rate_provider
        self._wallets: dict[str, Wallet] = {}
        for code, wallet in (wallets or {}).items():
            code = self._normalize_currency(code)
            if not isinstance(wallet, Wallet):
                raise TypeError("Значение словаря должно быть объектом Wallet")
            if code != wallet.currency_code:
                raise ValueError("Ключ словаря не совпадает с валютой кошелька")
            if code in self._wallets:
                raise ValueError(f"Кошелёк {code} уже существует")
            self._wallets[code] = wallet

    @property
    def user_id(self) -> int:
        """Вернуть неизменяемый идентификатор пользователя."""
        return self._user_id

    @property
    def user(self) -> User:
        """Вернуть владельца портфеля без возможности замены."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Вернуть копию словаря кошельков."""
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> None:
        """Создать пустой кошелёк; отклонить повторное добавление."""
        code = self._normalize_currency(currency_code)
        if code in self._wallets:
            raise ValueError(f"Кошелёк {code} уже существует")
        self._wallets[code] = Wallet(code)

    def get_wallet(self, currency_code: str) -> Wallet:
        """Вернуть кошелёк или выбросить KeyError, если он отсутствует."""
        code = self._normalize_currency(currency_code)
        if code not in self._wallets:
            raise KeyError(f"Кошелёк {code} не найден")
        return self._wallets[code]

    def get_total_value(self, base_currency: str = REFERENCE_CURRENCY) -> float:
        """Оценить ненулевые кошельки по свежему кешу; пробросить ошибку TTL."""
        base_currency = self._normalize_currency(base_currency)
        provider = self._rate_provider
        if provider is None:
            from valutatrade_hub.core.utils import RateService
            from valutatrade_hub.infra.database import JsonStorage

            provider = RateService(JsonStorage()).get_rate
        values = []
        for code, wallet in self._wallets.items():
            if wallet.balance:
                rate = Wallet._validate_amount(provider(code, base_currency)["rate"])
                values.append(wallet.balance * rate)
        try:
            total = math.fsum(values)
        except OverflowError:
            raise ValueError("Стоимость портфеля слишком велика") from None
        if not math.isfinite(total):
            raise ValueError("Стоимость портфеля слишком велика")
        return total

    @staticmethod
    def _normalize_currency(currency_code: str) -> str:
        return get_currency(currency_code).code
