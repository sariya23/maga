SUPPORTED_TYPES = {"int", "str", "bool"}


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


def create_table(metadata, table_name, columns):
    if table_name in metadata:
        print(f'Ошибка: Таблица "{table_name}" уже существует.')
        return metadata

    parsed_columns = []
    has_id = False

    for column in columns:
        if ":" not in column:
            print(f"Некорректное значение: {column}. Попробуйте снова.")
            return metadata

        column_name, column_type = column.split(":", 1)

        if not column_name or not column_type:
            print(f"Некорректное значение: {column}. Попробуйте снова.")
            return metadata

        if column_type not in SUPPORTED_TYPES:
            print(f"Некорректное значение: {column}. Попробуйте снова.")
            return metadata

        if column_name.lower() == "id":
            if has_id:
                print("Некорректное значение: ID указан несколько раз.")
                return metadata

            if column_type != "int":
                print("Некорректное значение: ID должен иметь тип int.")
                return metadata

            has_id = True
            column_name = "ID"

        if any(
            existing["name"].lower() == column_name.lower()
            for existing in parsed_columns
        ):
            print(
                f"Некорректное значение: столбец "
                f'"{column_name}" указан несколько раз.'
            )
            return metadata

        parsed_columns.append({
            "name": column_name,
            "type": column_type,
        })

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


def drop_table(metadata, table_name):
    if table_name not in metadata:
        print(f'Ошибка: Таблица "{table_name}" не существует.')
        return metadata

    del metadata[table_name]

    print(f'Таблица "{table_name}" успешно удалена.')

    return metadata


def insert(metadata, table_name, values, table_data):
    if table_name not in metadata:
        raise ValueError(
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
            f"Ожидалось значений: {len(columns_without_id)}, "
            f"получено: {len(values)}."
        )

    for column, value in zip(columns_without_id, values):
        if not validate_value(value, column["type"]):
            raise ValueError(
                f'Некорректный тип значения для столбца '
                f'"{column["name"]}". '
                f'Ожидается {column["type"]}.'
            )

    new_id = max(
        (row["ID"] for row in table_data),
        default=0,
    ) + 1

    record = {
        "ID": new_id,
    }

    for column, value in zip(columns_without_id, values):
        record[column["name"]] = value

    table_data.append(record)

    return table_data, new_id


def select(table_data, where_clause=None):
    if where_clause is None:
        return table_data

    column, value = next(iter(where_clause.items()))

    return [
        row
        for row in table_data
        if row.get(column) == value
    ]


def update(
    metadata,
    table_name,
    table_data,
    set_clause,
    where_clause,
):
    if table_name not in metadata:
        raise ValueError(
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
        raise ValueError(
            f'Столбца "{set_column}" не существует.'
        )

    if where_column not in column_types:
        raise ValueError(
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
            f'Некорректный тип значения для столбца '
            f'"{set_column}". '
            f'Ожидается {column_types[set_column]}.'
        )

    if not validate_value(
        where_value,
        column_types[where_column],
    ):
        raise ValueError(
            f'Некорректный тип значения для столбца '
            f'"{where_column}". '
            f'Ожидается {column_types[where_column]}.'
        )

    updated_ids = []

    for row in table_data:
        if row.get(where_column) == where_value:
            row[set_column] = set_value
            updated_ids.append(row["ID"])

    return table_data, updated_ids


def delete(
    metadata,
    table_name,
    table_data,
    where_clause,
):
    if table_name not in metadata:
        raise ValueError(
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
        raise ValueError(
            f'Столбца "{where_column}" не существует.'
        )

    if not validate_value(
        where_value,
        column_types[where_column],
    ):
        raise ValueError(
            f'Некорректный тип значения для столбца '
            f'"{where_column}". '
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