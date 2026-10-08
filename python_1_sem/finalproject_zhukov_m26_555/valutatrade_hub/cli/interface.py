import argparse
import os
import shlex
import sys
from pathlib import Path

from dotenv import load_dotenv
from prettytable import PrettyTable

from valutatrade_hub.core.constants import REFERENCE_CURRENCY
from valutatrade_hub.core.currencies import supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import CoreService
from valutatrade_hub.infra.settings import PROJECT_ROOT
from valutatrade_hub.logging_config import configure_parser_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.scheduler import run_scheduler
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.parser_service.views import cached_rates


class CommandError(ValueError):
    """Ошибка разбора команды без завершения интерактивной сессии."""


class CommandParser(argparse.ArgumentParser):
    """Парсер, преобразующий ошибки аргументов в CommandError."""

    def error(self, message: str) -> None:
        """Передать ошибку аргументов обработчику интерактивной сессии."""
        raise CommandError(message)


def build_parser() -> argparse.ArgumentParser:
    """Создать парсер всех команд приложения."""
    parser = CommandParser(
        prog="valutatrade", description="Виртуальный валютный портфель"
    )
    parser.add_argument(
        "--data-dir", help="Каталог JSON-файлов (по умолчанию из config.json)"
    )
    commands = parser.add_subparsers(dest="command")
    for name, description in (
        ("register", "Зарегистрироваться"),
        ("login", "Войти в систему"),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument("--username", required=True)
        command.add_argument("--password", required=True)
    portfolio = commands.add_parser("show-portfolio", help="Показать портфель")
    portfolio.add_argument(
        "--base", help="Базовая валюта (по умолчанию из config.json)"
    )
    for name, description in (("buy", "Купить валюту"), ("sell", "Продать валюту")):
        command = commands.add_parser(name, help=description)
        command.add_argument("--currency", required=True)
        command.add_argument("--amount", required=True, type=parse_amount)
    rate = commands.add_parser("get-rate", help="Получить курс валюты")
    rate.add_argument("--from", dest="from_currency", required=True)
    rate.add_argument("--to", dest="to_currency", required=True)
    update = commands.add_parser("update-rates", help="Обновить курсы из API")
    update.add_argument("--source", choices=("coingecko", "exchangerate"))
    schedule = commands.add_parser(
        "schedule-rates", help="Периодически обновлять курсы"
    )
    schedule.add_argument(
        "--interval", type=float, default=None, help="Интервал в секундах"
    )
    show = commands.add_parser("show-rates", help="Показать локальный кеш курсов")
    show.add_argument("--currency")
    show.add_argument("--top", type=int)
    show.add_argument("--base", default=REFERENCE_CURRENCY)
    help_command = commands.add_parser("help", help="Справка по командам")
    help_command.add_argument(
        "topic",
        nargs="?",
        choices=(
            "register",
            "login",
            "show-portfolio",
            "buy",
            "sell",
            "get-rate",
            "update-rates",
            "show-rates",
            "schedule-rates",
        ),
    )
    commands.add_parser("exit", help="Завершить сессию")
    return parser


def parse_amount(value: str) -> float:
    """Преобразовать аргумент суммы в число для доменной проверки."""
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "'amount' должен быть положительным числом"
        ) from None


def error_message(error: Exception) -> str:
    """Подготовить понятное пользователю сообщение об исключении."""
    if isinstance(error, InsufficientFundsError):
        return str(error)
    if isinstance(error, CurrencyNotFoundError):
        return (
            f"{error}. Поддерживаемые валюты: {', '.join(supported_codes())}. "
            "Справка: help get-rate"
        )
    if isinstance(error, ApiRequestError):
        return f"{error}. Повторите попытку позже или проверьте подключение к сети."
    return f"Ошибка: {error}"


class CLI:
    """Разбор команд и отображение результатов сервисов."""

    def __init__(
        self, service: CoreService, config: ParserConfig | None = None
    ) -> None:
        self.service = service
        self.parser = build_parser()
        self.config = config or ParserConfig(
            RATES_FILE_PATH=str(
                service.storage.data_dir / service.settings.get("RATES_FILE")
            ),
            HISTORY_FILE_PATH=str(service.storage.data_dir / "exchange_rates.json"),
        )
        self.rate_storage = RatesStorage(self.config)
        self.exit_code = 0

    def updater(self, source=None) -> RatesUpdater:
        """Собрать обновление курсов для выбранных API-источников."""
        configure_parser_logging()
        clients = []
        if source in (None, "coingecko"):
            clients.append(CoinGeckoClient(self.config))
        if source in (None, "exchangerate"):
            clients.append(ExchangeRateApiClient(self.config))
        return RatesUpdater(clients, self.rate_storage)

    def execute(self, args: argparse.Namespace) -> bool:
        """Выполнить команду; вернуть False при запросе выхода."""
        if args.command == "exit":
            return False
        if args.command in (None, "help"):
            if getattr(args, "topic", None):
                try:
                    self.parser.parse_args([args.topic, "--help"])
                except SystemExit:
                    pass
            else:
                self.parser.print_help()
        elif args.command == "update-rates":
            result = self.updater(args.source).run_update()
            print(
                f"Обновлено курсов: {result['updated']}. Последняя проверка: {result['last_refresh']}"
            )
            if result["errors"]:
                self.exit_code = 1
                print("Обновление завершено с ошибками. Подробности: logs/parser.log")
                for error in result["errors"]:
                    print(error)
        elif args.command == "schedule-rates":
            try:
                run_scheduler(
                    self.updater(),
                    self.config.UPDATE_INTERVAL
                    if args.interval is None
                    else args.interval,
                )
            except KeyboardInterrupt:
                print("Планировщик остановлен.")
        elif args.command == "show-rates":
            cache = self.rate_storage.read_cache()
            rows = cached_rates(
                cache,
                self.service.settings.get("RATES_TTL_SECONDS"),
                args.currency,
                args.top,
                args.base,
            )
            print(
                f"Курсы из кеша (последняя проверка: {cache.get('last_refresh', '—')}):"
            )
            table = PrettyTable(["Пара", "Курс", "Обновлено (UTC)", "Статус"])
            table.align = "l"
            for row in rows:
                table.add_row(
                    [
                        row["pair"],
                        f"{row['rate']:.8f}",
                        row["updated_at"],
                        "устарел; выполните update-rates"
                        if row["stale"]
                        else "актуален",
                    ]
                )
            print(table)
        elif args.command == "register":
            user = self.service.register(args.username, args.password)
            print(
                f"Пользователь '{user['username']}' зарегистрирован "
                f"(id={user['user_id']}). Войдите: "
                f"login --username {shlex.quote(user['username'])} --password ****"
            )
        elif args.command == "login":
            user = self.service.login(args.username, args.password)
            print(f"Вы вошли как '{user['username']}'")
        elif args.command == "show-portfolio":
            result = self.service.show_portfolio(args.base)
            base = result["base_currency"]
            print(f"Портфель пользователя '{result['username']}' (база: {base}):")
            if not result["wallets"]:
                print("В портфеле пока нет кошельков.")
            for wallet in result["wallets"]:
                print(
                    f"- {wallet['currency_code']}: {wallet['balance']:.4f} "
                    f"→ {wallet['value']:,.2f} {base}"
                )
            print("---------------------------------")
            print(f"ИТОГО: {result['total']:,.2f} {base}")
        elif args.command in ("buy", "sell"):
            action = self.service.buy if args.command == "buy" else self.service.sell
            result = action(args.currency, args.amount)
            code = result["currency_code"]
            label = "Покупка" if args.command == "buy" else "Продажа"
            print(
                f"{label} выполнена: {result['amount']:.4f} {code} "
                f"по курсу {result['rate']:.8f} USD/{code}"
            )
            print("Изменения в портфеле:")
            print(
                f"- {code}: было {result['before']:.4f} → стало {result['after']:.4f}"
            )
            label = (
                "Оценочная стоимость покупки"
                if args.command == "buy"
                else "Оценочная выручка"
            )
            print(f"{label}: {result['value']:,.2f} USD")
        elif args.command == "get-rate":
            result = self.service.get_rate(args.from_currency, args.to_currency)
            source, target = result["from_currency"], result["to_currency"]
            print(
                f"Курс {source}→{target}: {result['rate']:.8f} "
                f"(обновлено: {result['updated_at']})"
            )
            print(f"Обратный курс {target}→{source}: {1 / result['rate']:.8f}")
        return True

    def run(self) -> None:
        """Читать команды до выхода, обрабатывая ошибки без потери сессии."""
        print("ValutaTrade Hub. Курсы из локального кеша Parser Service.")
        print(
            "Команды: register, login, show-portfolio, buy, sell, get-rate, update-rates, show-rates, schedule-rates, help, exit."
        )
        while True:
            try:
                line = input("> ").strip()
                if not line:
                    continue
                args = self.parser.parse_args(shlex.split(line))
                if not self.execute(args):
                    return
            except EOFError:
                return
            except KeyboardInterrupt:
                print()
                return
            except SystemExit as exc:
                # argparse завершает обработку --help; сессия должна продолжиться.
                if exc.code:
                    print("Ошибка аргументов команды")
            except (ValueError, TypeError, OSError) as exc:
                print(error_message(exc))


def main(argv: list[str] | None = None) -> int:
    """Загрузить окружение, собрать сервисы и вернуть код завершения CLI."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        load_dotenv(PROJECT_ROOT / ".env")
        service = CoreService(args.data_dir)
        directory = Path(service.storage.data_dir)
        config = ParserConfig(
            EXCHANGERATE_API_KEY=(
                os.getenv("EXCHANGERATE_API_KEY") or os.getenv("EXCHANGE_RATE_API")
            ),
            RATES_FILE_PATH=str(directory / service.settings.get("RATES_FILE")),
            HISTORY_FILE_PATH=str(directory / "exchange_rates.json"),
        )
        cli = CLI(service, config)
        if args.command is None:
            cli.run()
        else:
            cli.execute(args)
    except (ValueError, TypeError, OSError) as exc:
        print(error_message(exc), file=sys.stderr)
        return 1
    return cli.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
