import hashlib
import hmac
import math
from datetime import datetime
from typing import ClassVar

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
)


class User:
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
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self) -> dict[str, int | str]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        self._hashed_password = self._hash_password(new_password)

    def verify_password(self, password: str) -> bool:
        if not isinstance(password, str):
            raise TypeError("Пароль должен быть строкой")
        return hmac.compare_digest(
            self._hash_password(password).encode("utf-8"),
            self.hashed_password.encode("utf-8"),
        )

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256((password + self.salt).encode("utf-8")).hexdigest()


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self._currency_code = get_currency(currency_code).code
        self.balance = balance

    @property
    def currency_code(self) -> str:
        return self._currency_code

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        value = self._validate_number(value)
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = value

    def deposit(self, amount: float) -> None:
        amount = self._validate_amount(amount)
        self.balance = self.balance + amount

    def withdraw(self, amount: float) -> None:
        amount = self._validate_amount(amount)
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount, self.currency_code)
        self.balance = self.balance - amount

    def get_balance_info(self) -> dict[str, str | float]:
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
    exchange_rates: ClassVar[dict[str, float]] = {
        "USD": 1.0,
        "EUR": 1.1,
        "RUB": 0.01,
        "BTC": 60000.0,
        "ETH": 3000.0,
    }

    def __init__(
        self,
        user_id: int,
        user: User,
        wallets: dict[str, Wallet] | None = None,
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
        return self._user_id

    @property
    def user(self) -> User:
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> None:
        code = self._normalize_currency(currency_code)
        if code in self._wallets:
            raise ValueError(f"Кошелёк {code} уже существует")
        self._wallets[code] = Wallet(code)

    def get_wallet(self, currency_code: str) -> Wallet:
        code = self._normalize_currency(currency_code)
        if code not in self._wallets:
            raise KeyError(f"Кошелёк {code} не найден")
        return self._wallets[code]

    def get_total_value(self, base_currency: str = "USD") -> float:
        base_currency = self._normalize_currency(base_currency)
        if base_currency not in self.exchange_rates:
            raise CurrencyNotFoundError(base_currency)
        base_rate = self.exchange_rates[base_currency]
        values = []
        for code, wallet in self._wallets.items():
            if wallet.balance == 0:
                continue
            if code not in self.exchange_rates:
                raise CurrencyNotFoundError(code)
            values.append(wallet.balance * (self.exchange_rates[code] / base_rate))
        return math.fsum(values)

    @staticmethod
    def _normalize_currency(currency_code: str) -> str:
        return get_currency(currency_code).code
