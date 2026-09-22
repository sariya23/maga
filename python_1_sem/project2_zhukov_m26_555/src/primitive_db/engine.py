import re
import shlex

from prettytable import PrettyTable

from src.primitive_db.core import (
    create_table,
    delete,
    drop_table,
    insert,
    select,
    update,
)
from src.primitive_db.parser import (
    parse_condition,
    parse_insert,
)
from src.primitive_db.utils import (
    load_metadata,
    load_table_data,
    save_metadata,
    save_table_data,
)

METADATA_FILE = "db_meta.json"


def print_help():
    print("\n***База данных***")

    print("\nУправление таблицами:")
    print(
        "<command> create_table <имя_таблицы> "
        "<столбец1:тип> <столбец2:тип> .. "
        "- создать таблицу"
    )
    print(
        "<command> list_tables "
        "- показать список всех таблиц"
    )
    print(
        "<command> drop_table <имя_таблицы> "
        "- удалить таблицу"
    )

    print("\nОперации с данными:")
    print(
        "<command> insert into <имя_таблицы> "
        "values (<значение1>, <значение2>, ...) "
        "- создать запись"
    )
    print(
        "<command> select from <имя_таблицы> "
        "where <столбец> = <значение> "
        "- прочитать записи по условию"
    )
    print(
        "<command> select from <имя_таблицы> "
        "- прочитать все записи"
    )
    print(
        "<command> update <имя_таблицы> "
        "set <столбец> = <значение> "
        "where <столбец> = <значение> "
        "- обновить запись"
    )
    print(
        "<command> delete from <имя_таблицы> "
        "where <столбец> = <значение> "
        "- удалить запись"
    )
    print(
        "<command> info <имя_таблицы> "
        "- вывести информацию о таблице"
    )

    print("\nОбщие команды:")
    print(
        "<command> exit - выход из программы"
    )
    print(
        "<command> help - справочная информация\n"
    )


def list_tables(metadata):
    if not metadata:
        print("Таблиц нет.")
        return

    for table_name in metadata:
        print(f"- {table_name}")


def print_table(rows, columns):
    table = PrettyTable()

    column_names = [
        column["name"]
        for column in columns
    ]

    table.field_names = column_names

    for row in rows:
        table.add_row([
            row.get(column)
            for column in column_names
        ])

    print(table)


def handle_insert(user_input, metadata):
    table_name, values = parse_insert(user_input)

    if table_name not in metadata:
        raise ValueError(
            f'Таблица "{table_name}" не существует.'
        )

    table_data = load_table_data(table_name)

    table_data, new_id = insert(
        metadata,
        table_name,
        values,
        table_data,
    )

    save_table_data(
        table_name,
        table_data,
    )

    print(
        f'Запись с ID={new_id} успешно добавлена '
        f'в таблицу "{table_name}".'
    )


def handle_select(user_input, metadata):
    pattern = (
        r"^select\s+from\s+(\w+)"
        r"(?:\s+where\s+(.+))?$"
    )

    match = re.match(
        pattern,
        user_input,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Некорректная команда select."
        )

    table_name = match.group(1)
    condition = match.group(2)

    if table_name not in metadata:
        raise ValueError(
            f'Таблица "{table_name}" не существует.'
        )

    table_data = load_table_data(table_name)

    where_clause = None

    if condition:
        where_clause = parse_condition(condition)

        column, value = next(
            iter(where_clause.items())
        )

        columns = {
            item["name"]: item["type"]
            for item in metadata[table_name]["columns"]
        }

        if column not in columns:
            raise ValueError(
                f'Столбца "{column}" не существует.'
            )

    rows = select(
        table_data,
        where_clause,
    )

    print_table(
        rows,
        metadata[table_name]["columns"],
    )


def handle_update(user_input, metadata):
    pattern = (
        r"^update\s+(\w+)\s+"
        r"set\s+(.+?)\s+"
        r"where\s+(.+)$"
    )

    match = re.match(
        pattern,
        user_input,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Некорректная команда update."
        )

    table_name = match.group(1)

    if table_name not in metadata:
        raise ValueError(
            f'Таблица "{table_name}" не существует.'
        )

    set_clause = parse_condition(
        match.group(2)
    )

    where_clause = parse_condition(
        match.group(3)
    )

    table_data = load_table_data(
        table_name
    )

    table_data, updated_ids = update(
        metadata,
        table_name,
        table_data,
        set_clause,
        where_clause,
    )

    if not updated_ids:
        print("Подходящие записи не найдены.")
        return

    save_table_data(
        table_name,
        table_data,
    )

    for record_id in updated_ids:
        print(
            f'Запись с ID={record_id} '
            f'в таблице "{table_name}" '
            f"успешно обновлена."
        )


def handle_delete(user_input, metadata):
    pattern = (
        r"^delete\s+from\s+(\w+)"
        r"\s+where\s+(.+)$"
    )

    match = re.match(
        pattern,
        user_input,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Некорректная команда delete."
        )

    table_name = match.group(1)

    if table_name not in metadata:
        raise ValueError(
            f'Таблица "{table_name}" не существует.'
        )

    where_clause = parse_condition(
        match.group(2)
    )

    table_data = load_table_data(
        table_name
    )

    table_data, deleted_ids = delete(
        metadata,
        table_name,
        table_data,
        where_clause,
    )

    if not deleted_ids:
        print("Подходящие записи не найдены.")
        return

    save_table_data(
        table_name,
        table_data,
    )

    for record_id in deleted_ids:
        print(
            f'Запись с ID={record_id} '
            f'успешно удалена из таблицы '
            f'"{table_name}".'
        )


def handle_info(user_input, metadata):
    args = shlex.split(user_input)

    if len(args) != 2:
        raise ValueError(
            "Использование: info <имя_таблицы>."
        )

    table_name = args[1]

    if table_name not in metadata:
        raise ValueError(
            f'Таблица "{table_name}" не существует.'
        )

    table_data = load_table_data(
        table_name
    )

    columns = metadata[
        table_name
    ]["columns"]

    columns_string = ", ".join(
        f'{column["name"]}:{column["type"]}'
        for column in columns
    )

    print(f"Таблица: {table_name}")
    print(f"Столбцы: {columns_string}")
    print(
        f"Количество записей: "
        f"{len(table_data)}"
    )


def run():
    metadata = load_metadata(
        METADATA_FILE
    )

    print_help()

    while True:
        user_input = input(
            ">>> Введите команду: "
        ).strip()

        if not user_input:
            continue

        command = user_input.split(
            maxsplit=1
        )[0].lower()

        try:
            if command == "exit":
                break

            elif command == "help":
                print_help()

            elif command == "create_table":
                args = shlex.split(
                    user_input
                )

                if len(args) < 3:
                    print(
                        "Некорректное значение: "
                        "недостаточно аргументов. "
                        "Попробуйте снова."
                    )
                    continue

                table_name = args[1]
                columns = args[2:]

                table_existed = (
                    table_name in metadata
                )

                metadata = create_table(
                    metadata,
                    table_name,
                    columns,
                )

                if not table_existed and table_name in metadata:
                    save_metadata(
                        METADATA_FILE,
                        metadata,
                    )

            elif command == "drop_table":
                args = shlex.split(
                    user_input
                )

                if len(args) != 2:
                    print(
                        "Некорректное значение: "
                        "необходимо указать "
                        "имя таблицы. "
                        "Попробуйте снова."
                    )
                    continue

                table_name = args[1]

                table_existed = (
                    table_name in metadata
                )

                metadata = drop_table(
                    metadata,
                    table_name,
                )

                if table_existed:
                    save_metadata(
                        METADATA_FILE,
                        metadata,
                    )

            elif command == "list_tables":
                args = shlex.split(
                    user_input
                )

                if len(args) != 1:
                    print(
                        "Некорректное значение: "
                        f"{' '.join(args[1:])}. "
                        "Попробуйте снова."
                    )
                    continue

                list_tables(metadata)

            elif command == "insert":
                handle_insert(
                    user_input,
                    metadata,
                )

            elif command == "select":
                handle_select(
                    user_input,
                    metadata,
                )

            elif command == "update":
                handle_update(
                    user_input,
                    metadata,
                )

            elif command == "delete":
                handle_delete(
                    user_input,
                    metadata,
                )

            elif command == "info":
                handle_info(
                    user_input,
                    metadata,
                )

            else:
                print(
                    f"Функции {command} нет. "
                    "Попробуйте снова."
                )

        except ValueError as error:
            print(f"Ошибка: {error}")