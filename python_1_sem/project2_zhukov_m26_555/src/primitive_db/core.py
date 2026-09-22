SUPPORTED_TYPES = {"int", "str", "bool"}


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

        # Проверяем тип для ВСЕХ колонок, включая ID
        if column_type not in SUPPORTED_TYPES:
            print(f"Некорректное значение: {column}. Попробуйте снова.")
            return metadata

        # Проверяем ID
        if column_name.lower() == "id":
            if has_id:
                print("Некорректное значение: ID указан несколько раз.")
                return metadata

            has_id = True
            column_name = "ID"

        parsed_columns.append({
            "name": column_name,
            "type": column_type,
        })

    # Если ID пользователь не указал
    if not has_id:
        parsed_columns.insert(0, {
            "name": "ID",
            "type": "int",
        })

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