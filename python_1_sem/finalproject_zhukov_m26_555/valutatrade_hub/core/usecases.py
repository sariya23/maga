import math
import secrets
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import (
    DEFAULT_DATA_DIR,
    JsonStorage,
    RateService,
    RateUnavailableError,
    StorageError,
    validate_amount,
    validate_currency,
)


class CoreService:
    def __init__(self, data_dir: str | Path = DEFAULT_DATA_DIR) -> None:
        self.storage = JsonStorage(data_dir)
        self.rates = RateService(self.storage)
        self._current_user: User | None = None

    @staticmethod
    def _username(username: str) -> str:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        return username.strip()

    def _users(self) -> list[User]:
        users = []
        try:
            for row in self.storage.read("users"):
                users.append(User(
                    user_id=row["user_id"],
                    username=row["username"],
                    hashed_password=row["hashed_password"],
                    salt=row["salt"],
                    registration_date=datetime.fromisoformat(row["registration_date"]),
                ))
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

    def register(self, username: str, password: str) -> dict:
        username = self._username(username)
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        users = self._users()
        if any(user.username == username for user in users):
            raise ValueError(f"Имя пользователя '{username}' уже занято")
        portfolios = self.storage.read("portfolios")
        user = User(
            user_id=max((user.user_id for user in users), default=0) + 1,
            username=username,
            hashed_password="pending",
            salt=secrets.token_hex(16),
            registration_date=datetime.now(timezone.utc),
        )
        user.change_password(password)
        saved_users = [self._serialize_user(item) for item in users]
        self.storage.write("users", [*saved_users, self._serialize_user(user)])
        try:
            self.storage.write("portfolios", [
                *portfolios, {"user_id": user.user_id, "wallets": {}},
            ])
        except OSError:
            self.storage.write("users", saved_users)
            raise
        return user.get_user_info()

    def login(self, username: str, password: str) -> dict:
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

    def _load_portfolio(self) -> Portfolio:
        user = self._require_login()
        try:
            records = self.storage.read("portfolios")
            row = next((row for row in records if row["user_id"] == user.user_id), None)
            if row is None:
                raise StorageError("Портфель пользователя не найден")
            wallets = {
                code: Wallet(code, entry["balance"])
                for code, entry in row["wallets"].items()
            }
            return Portfolio(user.user_id, user, wallets)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise StorageError(f"Неверные данные в portfolios.json: {exc}") from exc

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        records = self.storage.read("portfolios")
        for index, row in enumerate(records):
            if row["user_id"] == portfolio.user_id:
                records[index] = {
                    "user_id": portfolio.user_id,
                    "wallets": {
                        code: {"balance": wallet.balance}
                        for code, wallet in portfolio.wallets.items()
                    },
                }
                self.storage.write("portfolios", records)
                return
        raise StorageError("Портфель пользователя не найден")

    def get_rate(self, from_currency: str, to_currency: str) -> dict:
        return self.rates.get_rate(from_currency, to_currency)

    def show_portfolio(self, base: str = "USD") -> dict:
        portfolio = self._load_portfolio()
        base = validate_currency(base)
        try:
            self.get_rate(base, "USD")
        except RateUnavailableError:
            raise ValueError(f"Неизвестная базовая валюта '{base}'") from None
        rows = []
        for code, wallet in portfolio.wallets.items():
            rate = self.get_rate(code, base)["rate"]
            value = wallet.balance * rate
            if not math.isfinite(value):
                raise ValueError("Стоимость портфеля слишком велика")
            rows.append({"currency_code": code, "balance": wallet.balance, "value": value})
        try:
            total = math.fsum(row["value"] for row in rows)
        except OverflowError:
            raise ValueError("Стоимость портфеля слишком велика") from None
        return {
            "username": portfolio.user.username, "base_currency": base,
            "wallets": rows, "total": total,
        }

    def buy(self, currency: str, amount: float) -> dict:
        return self._trade("buy", currency, amount)

    def sell(self, currency: str, amount: float) -> dict:
        return self._trade("sell", currency, amount)

    def _trade(self, operation: str, currency: str, amount: float) -> dict:
        self._require_login()
        code = validate_currency(currency)
        amount = validate_amount(amount)
        portfolio = self._load_portfolio()
        if operation == "sell":
            if code not in portfolio.wallets:
                raise ValueError(
                    f"У вас нет кошелька '{code}'. Добавьте валюту: "
                    "она создаётся автоматически при первой покупке."
                )
            balance = portfolio.get_wallet(code).balance
            if amount > balance:
                raise ValueError(
                    f"Недостаточно средств: доступно {balance:.4f} {code}, "
                    f"требуется {amount:.4f} {code}"
                )
        try:
            quote = self.get_rate(code, "USD")
        except RateUnavailableError:
            raise ValueError(f"Не удалось получить курс для {code}→USD") from None
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
        self._save_portfolio(portfolio)
        return {
            "operation": operation, "currency_code": code, "amount": amount,
            "before": before, "after": wallet.balance, "rate": quote["rate"],
            "value": value,
        }
