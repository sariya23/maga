"""Хранение метаданных и записей в JSON-файлах."""

import json
import os

from primitive_db.constants import DATA_DIR, JSON_INDENT


def validate_identifier(name):
    """Проверить имя таблицы или столбца."""
    if not name or not all(char.isalnum() or char == "_" for char in name):
        raise ValueError(f"Некорректное имя: {name}.")


def load_metadata(filepath):
    """Загрузить метаданные или вернуть пустую базу."""
    try:
        with open(filepath, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_metadata(filepath, data):
    """Сохранить структуру базы данных."""
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=JSON_INDENT)


def table_path(table_name):
    """Получить путь к файлу таблицы после проверки имени."""
    validate_identifier(table_name)
    return os.path.join(DATA_DIR, f"{table_name}.json")


def load_table_data(table_name):
    """Загрузить записи таблицы, по умолчанию пустой список."""
    try:
        with open(table_path(table_name), encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_table_data(table_name, data):
    """Сохранить записи таблицы."""
    filepath = table_path(table_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    save_metadata(filepath, data)


def delete_table_data(table_name):
    """Удалить файл записей вместе с таблицей."""
    try:
        os.remove(table_path(table_name))
    except FileNotFoundError:
        pass
