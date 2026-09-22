import shlex

import prompt

from src.primitive_db.core import create_table, drop_table
from src.primitive_db.utils import load_metadata, save_metadata


def greet_user() -> str:
    welcome = """
    project

    Первая попытка запустить проект!

    ***
    <command> exit - выйти из программы
    <command> help - справочная информация
    Введите команду: help

    <command> exit - выйти из программы
    <command> help - справочная информация
    Введите команду: _
    """
    cmd = prompt.string(welcome)
    return cmd


METADATA_FILE = "db_meta.json"


def print_help():
    print("\n***Процесс работы с таблицей***")
    print("Функции:")
    print(
        "<command> create_table <имя_таблицы> "
        "<столбец1:тип> .. - создать таблицу"
    )
    print(
        "<command> list_tables - показать список всех таблиц"
    )
    print(
        "<command> drop_table <имя_таблицы> - удалить таблицу"
    )

    print("\nОбщие команды:")
    print("<command> exit - выход из программы")
    print("<command> help - справочная информация\n")


def list_tables(metadata):
    if not metadata:
        print("Таблиц нет.")
        return

    for table_name in metadata:
        print(f"- {table_name}")


def run():
    metadata = load_metadata(METADATA_FILE)

    print_help()

    while True:
        user_input = input(">>>Введите команду: ")

        try:
            args = shlex.split(user_input)
        except ValueError:
            print("Некорректная команда. Попробуйте снова.")
            continue

        if not args:
            continue

        command = args[0]

        if command == "exit":
            break

        elif command == "help":
            print_help()

        elif command == "list_tables":
            if len(args) != 1:
                print(
                    f"Некорректное значение: {' '.join(args[1:])}. "
                    "Попробуйте снова."
                )
                continue

            list_tables(metadata)

        elif command == "create_table":
            if len(args) < 3:
                print(
                    "Некорректное значение: недостаточно аргументов. "
                    "Попробуйте снова."
                )
                continue

            table_name = args[1]
            columns = args[2:]

            old_metadata = metadata.copy()

            metadata = create_table(
                metadata,
                table_name,
                columns,
            )

            if metadata != old_metadata:
                save_metadata(METADATA_FILE, metadata)

        elif command == "drop_table":
            if len(args) != 2:
                print(
                    "Некорректное значение: необходимо указать имя таблицы. "
                    "Попробуйте снова."
                )
                continue

            table_name = args[1]

            if table_name not in metadata:
                drop_table(metadata, table_name)
                continue

            metadata = drop_table(metadata, table_name)
            save_metadata(METADATA_FILE, metadata)

        else:
            print(
                f"Функции {command} нет. Попробуйте снова."
            )