from src.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)

SUPPORTED_TYPES = {"int", "str", "bool"}

cache_result = create_cacher()


def validate_value(value, expected_type):
    type_map = {
        "int": int,
        "str": str,
        "bool": bool,
    }

    if expected_type not in type_map:
        return False

    if expected_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)

    return isinstance(value, type_map[expected_type])


@handle_db_errors
def create_table(metadata, table_name, columns):
    if table_name in metadata:
        raise ValueError(
            f'Таблица "{table_name}" уже существует.'
        )

    parsed_columns = []
    has_id = False

    for column in columns:
        if ":" not in column:
            raise ValueError(
                f"Некорректное значение: {column}."
            )

        column_name, column_type = column.split(":", 1)

        if not column_name or not column_type:
            raise ValueError(
                f"Некорректное значение: {column}."
            )

        if column_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"Некорректный тип: {column_type}."
            )

        if column_name.lower() == "id":
            if has_id:
                raise ValueError(
                    "ID указан несколько раз."
                )

            if column_type != "int":
                raise ValueError(
                    "ID должен иметь тип int."
                )

            has_id = True
            column_name = "ID"

        if any(
            existing["name"].lower()
            == column_name.lower()
            for existing in parsed_columns
        ):
            raise ValueError(
                f'Столбец "{column_name}" '
                f"указан несколько раз."
            )

        parsed_columns.append(
            {
                "name": column_name,
                "type": column_type,
            }
        )

    if not has_id:
        parsed_columns.insert(
            0,
            {
                "name": "ID",
                "type": "int",
            },
        )

    metadata[table_name] = {
        "columns": parsed_columns,
    }

    column_description = ", ".join(
        f"{column['name']}:{column['type']}"
        for column in parsed_columns
    )

    print(
        f'Таблица "{table_name}" успешно создана '
        f"со столбцами: {column_description}"
    )

    return metadata


@confirm_action("удаление таблицы")
@handle_db_errors
def drop_table(metadata, table_name):
    if table_name not in metadata:
        raise KeyError(
            f'Таблица "{table_name}" не существует.'
        )

    del metadata[table_name]

    print(
        f'Таблица "{table_name}" успешно удалена.'
    )

    return metadata


@log_time
@handle_db_errors
def insert(
    metadata,
    table_name,
    values,
    table_data,
):
    if table_name not in metadata:
        raise KeyError(
            f'Таблица "{table_name}" не существует.'
        )

    columns = metadata[table_name]["columns"]

    columns_without_id = [
        column
        for column in columns
        if column["name"].lower() != "id"
    ]

    if len(values) != len(columns_without_id):
        raise ValueError(
            f"Ожидалось значений: "
            f"{len(columns_without_id)}, "
            f"получено: {len(values)}."
        )

    for column, value in zip(
        columns_without_id,
        values,
    ):
        if not validate_value(
            value,
            column["type"],
        ):
            raise ValueError(
                f'Некорректный тип значения '
                f'для столбца "{column["name"]}". '
                f'Ожидается {column["type"]}.'
            )

    new_id = max(
        (
            row["ID"]
            for row in table_data
        ),
        default=0,
    ) + 1

    record = {
        "ID": new_id,
    }

    for column, value in zip(
        columns_without_id,
        values,
    ):
        record[column["name"]] = value

    table_data.append(record)

    return table_data, new_id


@log_time
@handle_db_errors
def select(
    table_data,
    where_clause=None,
):
    if where_clause is None:
        cache_key = (
            "select_all",
            str(table_data),
        )
    else:
        cache_key = (
            "select_where",
            str(table_data),
            tuple(where_clause.items()),
        )

    def get_result():
        if where_clause is None:
            return table_data

        column, value = next(
            iter(where_clause.items())
        )

        return [
            row
            for row in table_data
            if row.get(column) == value
        ]

    return cache_result(
        cache_key,
        get_result,
    )


@handle_db_errors
def update(
    metadata,
    table_name,
    table_data,
    set_clause,
    where_clause,
):
    if table_name not in metadata:
        raise KeyError(
            f'Таблица "{table_name}" не существует.'
        )

    columns = metadata[table_name]["columns"]

    column_types = {
        column["name"]: column["type"]
        for column in columns
    }

    set_column, set_value = next(
        iter(set_clause.items())
    )

    where_column, where_value = next(
        iter(where_clause.items())
    )

    if set_column not in column_types:
        raise KeyError(
            f'Столбца "{set_column}" не существует.'
        )

    if where_column not in column_types:
        raise KeyError(
            f'Столбца "{where_column}" не существует.'
        )

    if set_column == "ID":
        raise ValueError(
            "Изменять ID нельзя."
        )

    if not validate_value(
        set_value,
        column_types[set_column],
    ):
        raise ValueError(
            f'Некорректный тип значения '
            f'для столбца "{set_column}". '
            f'Ожидается {column_types[set_column]}.'
        )

    if not validate_value(
        where_value,
        column_types[where_column],
    ):
        raise ValueError(
            f'Некорректный тип значения '
            f'для столбца "{where_column}". '
            f'Ожидается {column_types[where_column]}.'
        )

    updated_ids = []

    for row in table_data:
        if row.get(where_column) == where_value:
            row[set_column] = set_value
            updated_ids.append(row["ID"])

    return table_data, updated_ids


@confirm_action("удаление записи")
@handle_db_errors
def delete(
    metadata,
    table_name,
    table_data,
    where_clause,
):
    if table_name not in metadata:
        raise KeyError(
            f'Таблица "{table_name}" не существует.'
        )

    columns = metadata[table_name]["columns"]

    column_types = {
        column["name"]: column["type"]
        for column in columns
    }

    where_column, where_value = next(
        iter(where_clause.items())
    )

    if where_column not in column_types:
        raise KeyError(
            f'Столбца "{where_column}" не существует.'
        )

    if not validate_value(
        where_value,
        column_types[where_column],
    ):
        raise ValueError(
            f'Некорректный тип значения '
            f'для столбца "{where_column}". '
            f'Ожидается {column_types[where_column]}.'
        )

    deleted_ids = [
        row["ID"]
        for row in table_data
        if row.get(where_column) == where_value
    ]

    new_data = [
        row
        for row in table_data
        if row.get(where_column) != where_value
    ]

    return new_data, deleted_ids