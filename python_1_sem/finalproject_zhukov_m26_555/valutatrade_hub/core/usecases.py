import math
import secrets
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.core.constants import REFERENCE_CURRENCY
from valutatrade_hub.core.exceptions import InsufficientFundsError, StorageError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import (
    RateService,
    validate_amount,
    validate_currency,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import JsonStorage
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import configure_logging


class CoreService:
    """Сценарии регистрации, сессии и операций с валютным портфелем."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.settings = SettingsLoader()
        self.storage = JsonStorage(data_dir)
        self.rates = RateService(self.storage)
        self._current_user: User | None = None
        configure_logging()

    @staticmethod
    def _username(username: str) -> str:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        return username.strip()

    def _users(self, records: list | None = None) -> list[User]:
        users = []
        try:
            for row in self.storage.read("users") if records is None else records:
                users.append(
                    User(
                        user_id=row["user_id"],
                        username=row["username"],
                        hashed_password=row["hashed_password"],
                        salt=row["salt"],
                        registration_date=datetime.fromisoformat(
                            row["registration_date"]
                        ),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Неверные данные в users.json: {exc}") from exc
        return users

    @staticmethod
    def _serialize_user(user: User) -> dict:
        return {
            **user.get_user_info(),
            "hashed_password": user.hashed_password,
            "salt": user.salt,
        }

    @log_action("REGISTER")
    def register(self, username: str, password: str) -> dict:
        """Создать пользователя и пустой портфель, проверив уникальность имени."""
        username = self._username(username)
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        with self.storage.transaction("users", "portfolios") as documents:
            users = self._users(documents["users"])
            if any(user.username == username for user in users):
                raise ValueError(f"Имя пользователя '{username}' уже занято")
            user = User(
                user_id=max((user.user_id for user in users), default=0) + 1,
                username=username,
                hashed_password="pending",
                salt=secrets.token_hex(16),
                registration_date=datetime.now(timezone.utc),
            )
            user.change_password(password)
            documents["users"].append(self._serialize_user(user))
            documents["portfolios"].append({"user_id": user.user_id, "wallets": {}})
        return user.get_user_info()

    @log_action("LOGIN")
    def login(self, username: str, password: str) -> dict:
        """Проверить пароль и установить пользователя текущей сессии."""
        username = self._username(username)
        user = next((user for user in self._users() if user.username == username), None)
        if user is None:
            raise ValueError(f"Пользователь '{username}' не найден")
        if not user.verify_password(password):
            raise ValueError("Неверный пароль")
        self._current_user = user
        return user.get_user_info()

    def _require_login(self) -> User:
        if self._current_user is None:
            raise ValueError("Сначала выполните login")
        return self._current_user

    def _load_portfolio(self, records: list | None = None) -> Portfolio:
        user = self._require_login()
        try:
            if records is None:
                records = self.storage.read("portfolios")
            row = next((row for row in records if row["user_id"] == user.user_id), None)
            if row is None:
                raise StorageError("Портфель пользователя не найден")
            wallets = {
                code: Wallet(code, entry["balance"])
                for code, entry in row["wallets"].items()
            }
            return Portfolio(user.user_id, user, wallets, rate_provider=self.get_rate)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise StorageError(f"Неверные данные в portfolios.json: {exc}") from exc

    def _save_portfolio(self, portfolio: Portfolio, records: list) -> None:
        for index, row in enumerate(records):
            if row["user_id"] == portfolio.user_id:
                records[index] = {
                    "user_id": portfolio.user_id,
                    "wallets": {
                        code: {"balance": wallet.balance}
                        for code, wallet in portfolio.wallets.items()
                    },
                }
                return
        raise StorageError("Портфель пользователя не найден")

    def get_rate(self, from_currency: str, to_currency: str) -> dict:
        """Вернуть свежую котировку пары или доменную ошибку."""
        return self.rates.get_rate(from_currency, to_currency)

    def show_portfolio(self, base: str | None = None) -> dict:
        """Оценить кошельки текущего пользователя в выбранной валюте."""
        portfolio = self._load_portfolio()
        base = validate_currency(
            base if base is not None else self.settings.get("DEFAULT_BASE_CURRENCY")
        )
        rows = []
        for code, wallet in portfolio.wallets.items():
            rate = self.get_rate(code, base)["rate"]
            value = wallet.balance * rate
            if not math.isfinite(value):
                raise ValueError("Стоимость портфеля слишком велика")
            rows.append(
                {"currency_code": code, "balance": wallet.balance, "value": value}
            )
        try:
            total = math.fsum(row["value"] for row in rows)
        except OverflowError:
            raise ValueError("Стоимость портфеля слишком велика") from None
        return {
            "username": portfolio.user.username,
            "base_currency": base,
            "wallets": rows,
            "total": total,
        }

    @log_action("BUY", verbose=True)
    def buy(self, currency: str, amount: float) -> dict:
        """Добавить валюту в кошелёк и вернуть оценочную стоимость покупки."""
        return self._trade("buy", currency, amount)

    @log_action("SELL", verbose=True)
    def sell(self, currency: str, amount: float) -> dict:
        """Списать валюту при достаточном остатке и вернуть оценочную выручку."""
        return self._trade("sell", currency, amount)

    def _trade(self, operation: str, currency: str, amount: float) -> dict:
        self._require_login()
        code = validate_currency(currency)
        amount = validate_amount(amount)
        with self.storage.transaction("portfolios") as documents:
            portfolio = self._load_portfolio(documents["portfolios"])
            result = self._execute_trade(portfolio, operation, code, amount)
            self._save_portfolio(portfolio, documents["portfolios"])
        return result

    def _execute_trade(
        self, portfolio: Portfolio, operation: str, code: str, amount: float
    ) -> dict:
        if operation == "sell":
            if code not in portfolio.wallets:
                raise InsufficientFundsError(0.0, amount, code)
            balance = portfolio.get_wallet(code).balance
            if amount > balance:
                raise InsufficientFundsError(balance, amount, code)
        quote = self.get_rate(code, REFERENCE_CURRENCY)
        value = amount * quote["rate"]
        if not math.isfinite(value):
            raise ValueError("Стоимость сделки слишком велика")
        if code not in portfolio.wallets:
            portfolio.add_currency(code)
        wallet = portfolio.get_wallet(code)
        before = wallet.balance
        if operation == "buy":
            wallet.deposit(amount)
        else:
            wallet.withdraw(amount)
        return {
            "operation": operation,
            "currency_code": code,
            "amount": amount,
            "before": before,
            "after": wallet.balance,
            "rate": quote["rate"],
            "value": value,
            "base": REFERENCE_CURRENCY,
        }
