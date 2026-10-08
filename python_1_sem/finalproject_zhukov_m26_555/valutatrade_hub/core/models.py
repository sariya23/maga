import hashlib
import hmac
import math
from datetime import datetime


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
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code = currency_code.strip().upper()
        self.balance = balance

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
            raise ValueError("Недостаточно средств")
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
