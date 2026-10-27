# Студент: Жуков Никита Романович.
# Вариант: 4.
# Условие варианта: «Помещения и стеллажи без связей с другими таблицами».
# Сессионный проект: адаптировать ProjectPostgreSQL (people/phones -> rooms/racks),
# реализовать просмотр, добавление, изменение и удаление помещений с учётом
# связанных стеллажей; просмотр/добавление/удаление стеллажей выбранного помещения;
# валидацию значений и защиту от SQL-инъекций. Дополнительно выполнены:
# постраничный просмотр и изменение стеллажей (необязательные задания 6–7).

"""Консольное приложение для работы с помещениями и стеллажами склада."""

import math
import sys

import psycopg2

from dbconnection import DbConnection
from project_config import ProjectConfig
from tables.rooms_table import RoomsTable
from tables.racks_table import RacksTable
from validation import (
    ROOM_FIELDS, RACK_FIELDS, ValidationError,
    validate_room, validate_rack,
)


PAGE_SIZE = 5


class CancelOperation(Exception):
    """Операция отменена по запросу пользователя."""


class ExitProgram(Exception):
    """Выход из вложенного меню."""


def input_text(prompt):
    value = input(prompt).strip()
    if value == "!":
        raise CancelOperation
    return value


def confirm(question):
    return input_text(question + " [да/нет]: ").lower() == "да"


def read_fields(specification, existing=None, validator=None):
    """Пользователь вводит только прикладные поля, не технические ключи.

    Пустой ввод при UPDATE оставляет прежнее значение; ! отменяет действие.
    """
    print("Для отмены введите !")
    fields = {}
    for key, label, parser in specification:
        old = existing[key] if existing is not None else None
        suffix = f" [{old}]" if old is not None else ""
        while True:
            raw = input_text(f"{label}{suffix}: ")
            if not raw and old is not None:
                raw = old
            try:
                fields[key] = parser(raw)
                break
            except ValidationError as err:
                print(f"Ошибка ввода: {err}")
    # Все числовые значения отдельно проверены. Проверяем пары min/max.
    if validator is validate_room:
        for minimum, maximum, label in (
            ("temperature_min", "temperature_max", "температуры"),
            ("humidity_min", "humidity_max", "влажности"),
        ):
            while fields[minimum] > fields[maximum]:
                print(f"Ошибка: минимальное значение {label} больше максимального.")
                key, pretty, parser = next(x for x in specification if x[0] == maximum)
                try:
                    fields[key] = parser(input_text(f"Введите {pretty.lower()} заново: "))
                except ValidationError as err:
                    print(f"Ошибка ввода: {err}")
    return validator(fields) if validator is not None else fields


def describe_db_error(exc):
    """Делаем ошибки PostgreSQL понятными, не показывая SQL и секреты."""
    code = getattr(exc, "pgcode", None)
    if code == "23505":
        return "Такой номер стеллажа уже существует в выбранном помещении."
    if code == "23503":
        return "Удаление запрещено: есть связанные записи. Сначала удалите их."
    if code == "23514":
        return "Ограничение целостности не выполнено. Проверьте вводимые значения."
    if code == "23502":
        return "Не заполнено обязательное поле."
    if code == "22003":
        return "Число не помещается в поле базы данных."
    if code == "42P01":
        return "Таблица не найдена; проверьте схему и права доступа."
    if isinstance(exc, psycopg2.OperationalError):
        return "Соединение с PostgreSQL потеряно. Проверьте сервер."
    return f"Операция не выполнена (ошибка PostgreSQL {code or 'неизвестная'})."


def show_room_row(i, room):
    return (
        f"{i:>2}. {room['name']} | объём {room['usable_volume']} м³ | "
        f"t {room['temperature_min']}..{room['temperature_max']} °C | "
        f"влажн. {room['humidity_min']}..{room['humidity_max']} %"
    )


def show_rack_row(i, rack):
    return (
        f"{i:>2}. Стеллаж №{rack['rack_number']} | мест: {rack['storage_places']} | "
        f"место (В×Ш×Д): {rack['place_height']}×{rack['place_width']}×"
        f"{rack['place_length']} м | нагрузка: {rack['max_total_load']} кг"
    )


def select_row(rows):
    """Номер берётся ИСКЛЮЧИТЕЛЬНО из видимого списка текущей страницы."""
    if not rows:
        print("На этой странице нет записей.")
        return None
    while True:
        value = input_text(f"Выберите № строки от 1 до {len(rows)} (или !): ")
        if not value.isdecimal():
            print("Введите порядковый номер строки целым числом.")
            continue
        if len(value) > 5:
            print("Слишком большой номер строки.")
            continue
        index = int(value)
        if 1 <= index <= len(rows):
            return rows[index - 1]
        print("Такой строки нет на текущей странице.")


class Main:
    def __init__(self, db):
        self.rooms = RoomsTable(db)
        self.racks = RacksTable(db)

    def db_init(self):
        # Не удаляем данные: IF NOT EXISTS безопасен при повторном запуске.
        self.rooms.create()
        self.racks.create()

    def main_cycle(self):
        while True:
            print("\n=== УЧЁТ ПОМЕЩЕНИЙ И СТЕЛЛАЖЕЙ (вариант 4) ===")
            print("1 — просмотр и управление помещениями")
            print("9 — выход")
            choice = input_text("Выбор: ")
            if choice == "9":
                return
            if choice == "1":
                self.rooms_menu()
            else:
                print("Неизвестный пункт меню.")

    def rooms_menu(self):
        page = 1
        while True:
            try:
                total = self.rooms.count()
                pages = max(1, math.ceil(total / PAGE_SIZE))
                page = min(page, pages)
                rows = self.rooms.page((page - 1) * PAGE_SIZE, PAGE_SIZE)
                print(f"\n=== ПОМЕЩЕНИЯ: страница {page}/{pages}, всего {total} ===")
                for i, room in enumerate(rows, 1):
                    print(show_room_row(i, room))
                if not rows:
                    print("Нет записей.")
                print("a — добавить, e — изменить, d — удалить, r — стеллажи помещения")
                print("n — следующая страница, p — предыдущая, b — главное меню, 9 — выход")
                choice = input_text("Выбор: ").lower()
                if choice == "b":
                    return
                if choice == "9":
                    raise ExitProgram
                if choice == "n":
                    if page < pages:
                        page += 1
                    else:
                        print("Это последняя страница.")
                    continue
                if choice == "p":
                    if page > 1:
                        page -= 1
                    else:
                        print("Это первая страница.")
                    continue
                if choice == "a":
                    self.add_room()
                    continue
                if choice in ("e", "d", "r"):
                    chosen = select_row(rows)
                    if chosen is None:
                        continue
                    if choice == "e":
                        self.edit_room(chosen)
                    elif choice == "d":
                        self.delete_room(chosen)
                    else:
                        self.racks_menu(chosen["room_id"])
                else:
                    print("Неизвестный пункт меню.")
            except CancelOperation:
                print("Операция отменена.")
            except psycopg2.Error as exc:
                print("Ошибка: " + describe_db_error(exc))

    def add_room(self):
        values = read_fields(ROOM_FIELDS, validator=validate_room)
        self.rooms.insert_one(values)
        print("Помещение добавлено.")

    def edit_room(self, room):
        values = read_fields(ROOM_FIELDS, existing=room, validator=validate_room)
        if self.rooms.update_one(room["room_id"], values):
            print("Помещение изменено.")
        else:
            print("Помещение уже удалено другим пользователем.")

    def delete_room(self, room):
        linked = self.racks.count_for_room(room["room_id"])
        if linked:
            print(
                f"Удаление запрещено: в помещении «{room['name']}» "
                f"находится {linked} стеллаж(ей). Сначала удалите стеллажи."
            )
            return
        if confirm(f"Удалить помещение «{room['name']}»?"):
            if self.rooms.delete_one(room["room_id"]):
                print("Помещение удалено.")
            else:
                print("Помещение уже отсутствует.")
        else:
            print("Удаление отменено.")

    def racks_menu(self, room_id):
        page = 1
        while True:
            try:
                room = self.rooms.get(room_id)
                if room is None:
                    print("Выбранное помещение больше не существует.")
                    return
                total = self.racks.count_for_room(room_id)
                pages = max(1, math.ceil(total / PAGE_SIZE))
                page = min(page, pages)
                rows = self.racks.page_for_room(room_id, (page - 1) * PAGE_SIZE, PAGE_SIZE)
                print(f"\n=== СТЕЛЛАЖИ: «{room['name']}», страница {page}/{pages}, всего {total} ===")
                for i, rack in enumerate(rows, 1):
                    print(show_rack_row(i, rack))
                if not rows:
                    print("Нет стеллажей.")
                print("a — добавить, e — изменить, d — удалить")
                print("n — следующая, p — предыдущая, b — помещения, 9 — выход")
                choice = input_text("Выбор: ").lower()
                if choice == "b":
                    return
                if choice == "9":
                    raise ExitProgram
                if choice == "n":
                    if page < pages:
                        page += 1
                    else:
                        print("Это последняя страница.")
                    continue
                if choice == "p":
                    if page > 1:
                        page -= 1
                    else:
                        print("Это первая страница.")
                    continue
                if choice == "a":
                    values = read_fields(RACK_FIELDS, validator=validate_rack)
                    self.racks.insert_one(room_id, values)
                    print("Стеллаж добавлен.")
                    continue
                if choice in ("e", "d"):
                    rack = select_row(rows)
                    if rack is None:
                        continue
                    if choice == "e":
                        values = read_fields(RACK_FIELDS, existing=rack, validator=validate_rack)
                        if self.racks.update_one(rack["rack_id"], room_id, values):
                            print("Стеллаж изменён.")
                        else:
                            print("Стеллаж больше не существует.")
                    elif confirm(f"Удалить стеллаж №{rack['rack_number']}?"):
                        if self.racks.delete_one(rack["rack_id"], room_id):
                            print("Стеллаж удалён.")
                        else:
                            print("Стеллаж больше не существует.")
                    else:
                        print("Удаление отменено.")
                else:
                    print("Неизвестный пункт меню.")
            except CancelOperation:
                print("Операция отменена.")
            except psycopg2.Error as exc:
                print("Ошибка: " + describe_db_error(exc))


def main():
    db = None
    try:
        config = ProjectConfig()
        db = DbConnection(config)
        app = Main(db)
        app.db_init()
        app.main_cycle()
        print("До свидания!")
        return 0
    except (KeyboardInterrupt, EOFError, ExitProgram):
        print("\nВыход из программы.")
        return 0
    except CancelOperation:
        print("Операция отменена. Программа завершена.")
        return 0
    except (psycopg2.Error, OSError, ValueError, KeyError) as err:
        if isinstance(err, psycopg2.Error):
            print("Ошибка подключения/инициализации: " + describe_db_error(err))
        else:
            print(f"Ошибка конфигурации: {err}")
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
