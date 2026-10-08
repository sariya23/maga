import argparse
import shlex
import sys

from valutatrade_hub.core.usecases import CoreService
from valutatrade_hub.core.utils import DEFAULT_DATA_DIR


class CommandError(ValueError):
    pass


class CommandParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CommandError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = CommandParser(prog="valutatrade", description="Виртуальный валютный портфель")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR),
                        help="Каталог JSON-файлов (по умолчанию data в проекте)")
    commands = parser.add_subparsers(dest="command")
    for name, description in (("register", "Зарегистрироваться"),
                              ("login", "Войти в систему")):
        command = commands.add_parser(name, help=description)
        command.add_argument("--username", required=True)
        command.add_argument("--password", required=True)
    portfolio = commands.add_parser("show-portfolio", help="Показать портфель")
    portfolio.add_argument("--base", default="USD")
    for name, description in (("buy", "Купить валюту"), ("sell", "Продать валюту")):
        command = commands.add_parser(name, help=description)
        command.add_argument("--currency", required=True)
        command.add_argument("--amount", required=True, type=parse_amount)
    rate = commands.add_parser("get-rate", help="Получить курс валюты")
    rate.add_argument("--from", dest="from_currency", required=True)
    rate.add_argument("--to", dest="to_currency", required=True)
    commands.add_parser("help", help="Список команд")
    commands.add_parser("exit", help="Завершить сессию")
    return parser


def parse_amount(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "'amount' должен быть положительным числом"
        ) from None


class CLI:
    def __init__(self, service: CoreService) -> None:
        self.service = service
        self.parser = build_parser()

    def execute(self, args: argparse.Namespace) -> bool:
        if args.command == "exit":
            return False
        if args.command in (None, "help"):
            self.parser.print_help()
        elif args.command == "register":
            user = self.service.register(args.username, args.password)
            print(f"Пользователь '{user['username']}' зарегистрирован "
                  f"(id={user['user_id']}). Войдите: "
                  f"login --username {shlex.quote(user['username'])} --password ****")
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
                print(f"- {wallet['currency_code']}: {wallet['balance']:.4f} "
                      f"→ {wallet['value']:,.2f} {base}")
            print("---------------------------------")
            print(f"ИТОГО: {result['total']:,.2f} {base}")
        elif args.command in ("buy", "sell"):
            action = self.service.buy if args.command == "buy" else self.service.sell
            result = action(args.currency, args.amount)
            code = result["currency_code"]
            label = "Покупка" if args.command == "buy" else "Продажа"
            print(f"{label} выполнена: {result['amount']:.4f} {code} "
                  f"по курсу {result['rate']:.8f} USD/{code}")
            print("Изменения в портфеле:")
            print(f"- {code}: было {result['before']:.4f} → стало {result['after']:.4f}")
            label = "Оценочная стоимость покупки" if args.command == "buy" else "Оценочная выручка"
            print(f"{label}: {result['value']:,.2f} USD")
        elif args.command == "get-rate":
            result = self.service.get_rate(args.from_currency, args.to_currency)
            source, target = result["from_currency"], result["to_currency"]
            print(f"Курс {source}→{target}: {result['rate']:.8f} "
                  f"(обновлено: {result['updated_at']})")
            print(f"Обратный курс {target}→{source}: {1 / result['rate']:.8f}")
        return True

    def run(self) -> None:
        print("ValutaTrade Hub. Учебный режим, Parser не подключён; используются кеш и заглушка.")
        print("Команды: register, login, show-portfolio, buy, sell, get-rate, help, exit.")
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
                print(f"Ошибка: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        cli = CLI(CoreService(args.data_dir))
        if args.command is None:
            cli.run()
        else:
            cli.execute(args)
    except (ValueError, TypeError, OSError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
