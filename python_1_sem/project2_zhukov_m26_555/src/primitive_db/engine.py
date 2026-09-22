import shlex

from prettytable import PrettyTable

from primitive_db.constants import META_FILE
from primitive_db.core import (
    create_table,
    delete,
    drop_table,
    insert,
    select,
    update,
    validate_value,
)
from primitive_db.parser import (
    parse_condition,
    parse_delete,
    parse_insert,
    parse_select,
    parse_update,
)
from primitive_db.utils import (
    load_metadata,
    load_table_data,
    save_metadata,
    save_table_data,
)


def print_help():
    """Вывести справку по командам."""
    print("\n***База данных***")

    print("\nУправление таблицами:")
    print(
        "<command> create_table <имя_таблицы> "
        "<столбец1:тип> <столбец2:тип> .. "
        "- создать таблицу"
    )
    print("<command> list_tables - показать список всех таблиц")
    print("<command> drop_table <имя_таблицы> - удалить таблицу")

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
    print("<command> select from <имя_таблицы> - прочитать все записи")
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
    print("<command> info <имя_таблицы> - вывести информацию о таблице")

    print("\nОбщие команды:")
    print("<command> help - справочная информация")
    print("<command> exit - выход из программы\n")


def list_tables(metadata):
    """Вывести список таблиц."""
    if not metadata:
        print("Таблиц нет.")
        return

    for table_name in metadata:
        print(f"- {table_name}")


def print_table(rows, columns):
    """Вывести записи в табличном виде."""
    table = PrettyTable()

    column_names = [column["name"] for column in columns]

    table.field_names = column_names

    for row in rows:
        table.add_row([row.get(column) for column in column_names])

    print(table)


def handle_insert(user_input, metadata):
    """Разобрать команду и выполнить операцию с таблицей."""
    table_name, values = parse_insert(user_input)

    table_data = load_table_data(table_name)

    result = insert(
        metadata,
        table_name,
        values,
        table_data,
    )

    if result is None:
        return

    table_data, new_id = result

    save_table_data(
        table_name,
        table_data,
    )

    print(f'Запись с ID={new_id} успешно добавлена в таблицу "{table_name}".')


def handle_select(user_input, metadata):
    """Разобрать команду и выполнить операцию с таблицей."""
    table_name, condition = parse_select(user_input)

    if table_name not in metadata:
        print(f'Ошибка: Таблица "{table_name}" не существует.')
        return

    table_data = load_table_data(table_name)

    where_clause = None

    if condition:
        where_clause = parse_condition(condition)

        column, value = next(iter(where_clause.items()))

        columns = {
            item["name"]: item["type"] for item in metadata[table_name]["columns"]
        }

        if column not in columns:
            print(f'Ошибка: Столбца "{column}" не существует.')
            return

    if where_clause and not validate_value(value, columns[column]):
        raise ValueError(f"Некорректный тип значения для столбца {column}.")

    rows = select(
        table_data,
        where_clause,
    )

    if rows is None:
        return

    print_table(
        rows,
        metadata[table_name]["columns"],
    )


def handle_update(user_input, metadata):
    """Разобрать команду и выполнить операцию с таблицей."""
    table_name, set_clause, where_clause = parse_update(user_input)

    table_data = load_table_data(table_name)

    result = update(
        metadata,
        table_name,
        table_data,
        set_clause,
        where_clause,
    )

    if result is None:
        return

    table_data, updated_ids = result

    if not updated_ids:
        print("Подходящие записи не найдены.")
        return

    save_table_data(
        table_name,
        table_data,
    )

    for record_id in updated_ids:
        print(f'Запись с ID={record_id} в таблице "{table_name}" успешно обновлена.')


def handle_delete(user_input, metadata):
    """Разобрать команду и выполнить операцию с таблицей."""
    table_name, where_clause = parse_delete(user_input)

    table_data = load_table_data(table_name)

    result = delete(
        metadata,
        table_name,
        table_data,
        where_clause,
    )

    if result is None:
        return

    table_data, deleted_ids = result

    if not deleted_ids:
        print("Подходящие записи не найдены.")
        return

    save_table_data(
        table_name,
        table_data,
    )

    for record_id in deleted_ids:
        print(f'Запись с ID={record_id} успешно удалена из таблицы "{table_name}".')


def handle_info(user_input, metadata):
    """Разобрать команду и выполнить операцию с таблицей."""
    args = shlex.split(user_input)

    if len(args) != 2:
        raise ValueError("Использование: info <имя_таблицы>.")

    table_name = args[1]

    if table_name not in metadata:
        print(f'Ошибка: Таблица "{table_name}" не существует.')
        return

    table_data = load_table_data(table_name)

    columns = metadata[table_name]["columns"]

    columns_string = ", ".join(
        f"{column['name']}:{column['type']}" for column in columns
    )

    print(f"Таблица: {table_name}")
    print(f"Столбцы: {columns_string}")
    print(f"Количество записей: {len(table_data)}")


def run():
    """Запустить интерактивный цикл команд."""
    metadata = load_metadata(META_FILE)

    print_help()

    while True:
        try:
            user_input = input(">>> Введите команду: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        command = user_input.split(maxsplit=1)[0].lower()

        try:
            if command == "exit":
                break

            elif command == "help":
                print_help()

            elif command == "create_table":
                args = shlex.split(user_input)

                if len(args) < 3:
                    print(
                        "Некорректное значение: "
                        "недостаточно аргументов. "
                        "Попробуйте снова."
                    )
                    continue

                table_name = args[1]
                columns = args[2:]

                result = create_table(
                    metadata,
                    table_name,
                    columns,
                )

                if result is None:
                    continue

                metadata = result

                save_metadata(
                    META_FILE,
                    metadata,
                )

            elif command == "drop_table":
                args = shlex.split(user_input)

                if len(args) != 2:
                    print(
                        "Некорректное значение: "
                        "необходимо указать "
                        "имя таблицы. "
                        "Попробуйте снова."
                    )
                    continue

                table_name = args[1]

                result = drop_table(
                    metadata,
                    table_name,
                )

                if result is None:
                    continue

                metadata = result

                save_metadata(
                    META_FILE,
                    metadata,
                )

            elif command == "list_tables":
                args = shlex.split(user_input)

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
                print(f"Функции {command} нет. Попробуйте снова.")

        except (EOFError, KeyboardInterrupt):
            print()
            break
        except (ValueError, OSError) as error:
            print(f"Ошибка: {error}")
