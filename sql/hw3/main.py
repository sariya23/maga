"""Консольный интерфейс: выбор только по строкам текущей страницы."""
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from hw3.dbconnection import AppError, DbConnection
from hw3.project_config import ProjectConfig
from hw3.tables.rooms_table import RoomsTable
from hw3.tables.racks_table import RacksTable
from hw3.validation import ValidationError, validate


class Cancelled(Exception):
    pass


def ask(prompt):
    value = input(prompt).strip()
    if value == '/отмена':
        raise Cancelled
    return value


def select_row(rows):
    if not rows:
        raise AppError('На странице нет записей для выбора.')
    while True:
        raw = ask('Номер строки на текущей странице (0 — отмена): ')
        if raw == '0':
            raise Cancelled
        if raw.isascii() and raw.isdigit() and len(raw) < 10 and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        print(f'Введите номер строки от 1 до {len(rows)}.')


def form(table, original=None):
    print('/отмена — отменить ввод.' + (' Enter — оставить текущее значение.' if original else ''))
    values = {}
    while True:
        for key, label, parser in table.fields:
            default = values.get(key, original[key] if original else None)
            while True:
                raw = ask(f'{label}' + (f' [{default}]' if default is not None else '') + ': ')
                try:
                    values[key] = parser(default if raw == '' and default is not None else raw)
                    break
                except ValidationError as error:
                    print(error)
        try:
            return validate(table.fields, values)
        except ValidationError as error:
            print(f'{error} Исправьте значения; Enter сохраняет введённое.')


class Main:
    def __init__(self, connection):
        self.connection = connection

    def browse(self, room=None):
        table = RoomsTable(self.connection) if room is None else RacksTable(self.connection, room['room_id'])
        page = 1
        while True:
            try:
                rows, page, pages, count = table.page(page)
                print('\n' + ('Помещения' if room is None else f'Стеллажи помещения «{room["name"]}»'))
                print(f'Страница {page}/{pages}. Записей: {count}.')
                print(' | '.join(['Строка'] + [label for _, label, _ in table.fields]))
                for position, row in enumerate(rows, 1):
                    print(' | '.join([str(position)] + [str(row[key]) for key, _, _ in table.fields]))
                if not rows:
                    print('Список пуст.')
                print('1 — добавить; 2 — изменить; 3 — удалить; n — следующая; p — предыдущая; r — обновить; 0 — назад')
                if room is None:
                    print('4 — стеллажи выбранного помещения')
                command = ask('Действие: ').lower()
                if command == '0':
                    return
                if command in ('n', 'p'):
                    target = page + (1 if command == 'n' else -1)
                    if 1 <= target <= pages:
                        page = target
                    else:
                        print('Это последняя страница.' if command == 'n' else 'Это первая страница.')
                elif command == 'r':
                    continue
                elif command == '1':
                    table.save(form(table))
                    print('Запись добавлена.')
                elif command == '2':
                    row = select_row(rows)
                    table.save(form(table, row), row)
                    print('Изменения сохранены.')
                elif command == '3':
                    row = select_row(rows)
                    label = row['name'] if room is None else f'стеллаж №{row["rack_number"]}'
                    if ask(f'Удалить «{label}»? Введите «да» для подтверждения: ').lower() == 'да':
                        table.delete(row)
                        print('Запись удалена.')
                    else:
                        print('Удаление отменено.')
                elif command == '4' and room is None:
                    self.browse(select_row(rows))
                else:
                    print('Неизвестное действие. Выберите команду из меню.')
            except Cancelled:
                print('Действие отменено.')
            except (AppError, ValidationError) as error:
                print(error)
                # Ошибку чтения нельзя повторять бесконечно без участия пользователя.
                if ask('Enter — повторить/обновить список, 0 — назад: ') == '0':
                    return

    def run(self):
        while True:
            try:
                print('\nСклад: 1 — помещения; 2 — создать таблицы; 3 — загрузить примеры из hw2; 0 — выход')
                command = ask('Действие: ')
                if command == '0':
                    return
                if command == '1':
                    self.browse()
                elif command == '2':
                    self.connection.initialize()
                    print('Таблицы готовы. Существующие данные сохранены.')
                elif command == '3':
                    self.connection.demo()
                    print('Добавлены пять помещений и пять стеллажей из hw2.')
                else:
                    print('Неизвестное действие.')
            except Cancelled:
                print('Действие отменено.')
            except (AppError, ValidationError) as error:
                print(error)


def main():
    connection = None
    try:
        connection = DbConnection(ProjectConfig())
        Main(connection).run()
    except (OSError, ValueError, yaml.YAMLError):
        print('Не удалось прочитать настройки. Проверьте hw3/config.yaml или WAREHOUSE_CONFIG.')
    except (EOFError, KeyboardInterrupt):
        print('\nВвод завершён. Несохранённая форма отменена.')
    finally:
        if connection is not None:
            connection.close()
    print('До свидания!')


if __name__ == '__main__':
    main()
