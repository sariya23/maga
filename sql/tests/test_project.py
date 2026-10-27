import io
import os
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from hw3.validation import ROOM_FIELDS, RACK_FIELDS, ValidationError, numeric, integer, name, validate
from hw3.main import select_row, Cancelled, Main
from hw3.dbconnection import DbConnection, AppError
from hw3.project_config import ProjectConfig
from hw3.tables.rooms_table import RoomsTable
from hw3.tables.racks_table import RacksTable

ROOM = dict(name='Склад', usable_volume='500', temperature_min='-10', temperature_max='25', humidity_min='0', humidity_max='100')
RACK = dict(rack_number='1', storage_places='20', place_height='1', place_width='1.2', place_length='0.8', max_total_load='2000')


class ValidationTests(unittest.TestCase):
    def test_numbers(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1e3', '0', '-1', '100000000000', '0.0001', "1'; DROP TABLE rooms;--"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                numeric(14, 3, positive=True)(value)
        self.assertEqual(numeric(14, 3, positive=True)('99999999999,999'), Decimal('99999999999.999'))
        self.assertEqual(numeric(5, 2, -273.15)('-273.15'), Decimal('-273.15'))
        for value in ('2147483648', '1.5', '-1', '0', '9' * 5000):
            with self.assertRaises(ValidationError):
                integer(value)

    def test_ranges_and_text(self):
        for changes in ({'humidity_max': '101'}, {'humidity_min': '51', 'humidity_max': '50'},
                        {'temperature_min': '26'}, {'temperature_min': '-273.16'}, {'temperature_max': '1000'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                validate(ROOM_FIELDS, ROOM | changes)
        for value in (' ', 'a\x00b', '\x1b[31m'):
            with self.assertRaises(ValidationError):
                name(value)
        self.assertEqual(name(" O'Reilly "), "O'Reilly")

    def test_selection_uses_displayed_row(self):
        rows = [{'room_id': 908}, {'room_id': 17}]
        with patch('builtins.input', side_effect=['abc', '-1', '9' * 5000, '3', '2']), redirect_stdout(io.StringIO()):
            self.assertEqual(select_row(rows), rows[1])
        with patch('builtins.input', return_value='0'), self.assertRaises(Cancelled):
            select_row(rows)


@unittest.skipUnless(os.environ.get('WAREHOUSE_TEST_DB') == '1', 'Нужна отдельная тестовая PostgreSQL: WAREHOUSE_TEST_DB=1')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.db = DbConnection(ProjectConfig())
        self.db.initialize()
        self.db.run(lambda cur: cur.execute('TRUNCATE racks, rooms RESTART IDENTITY'))
        self.rooms = RoomsTable(self.db)

    def tearDown(self):
        self.db.close()

    def test_crud_constraints_and_recovery(self):
        injection = "O'Reilly'); DROP TABLE rooms; --"
        self.rooms.save(ROOM | {'name': injection})
        room = self.rooms.page(1)[0][0]
        self.assertEqual(room['name'], injection)
        racks = RacksTable(self.db, room['room_id'])
        racks.save(RACK)
        with self.assertRaisesRegex(AppError, 'уже есть'):
            racks.save(RACK)
        rack = racks.page(1)[0][0]
        with self.assertRaisesRegex(AppError, 'связана'):
            self.rooms.delete(room)
        self.rooms.save(ROOM | {'name': 'Новое имя'}, room)
        with self.assertRaisesRegex(AppError, 'уже изменена'):
            self.rooms.save(ROOM, room)
        racks.save(RACK | {'rack_number': '2'}, rack)
        rack = racks.page(1)[0][0]
        self.assertEqual(rack['rack_number'], 2)
        racks.delete(rack)
        room = self.rooms.page(1)[0][0]
        self.rooms.delete(room)
        self.assertEqual(self.rooms.page(1)[3], 0)
        with self.assertRaises(AppError):
            racks.save(RACK)
        self.rooms.save(ROOM)

    def test_pages_and_scope(self):
        for i in range(12):
            self.rooms.save(ROOM | {'name': f'Склад {i:02}'})
        rows, current, pages, count = self.rooms.page(100)
        self.assertEqual((len(rows), current, pages, count), (2, 3, 3, 12))
        first, second = self.rooms.page(1)[0][:2]
        a, b = RacksTable(self.db, first['room_id']), RacksTable(self.db, second['room_id'])
        for i in range(7):
            a.save(RACK | {'rack_number': str(i + 1)})
        b.save(RACK)
        self.assertEqual((a.page(2)[3], len(a.page(2)[0]), b.page(1)[3]), (7, 2, 1))
        with self.assertRaises(AppError):
            b.delete(a.page(1)[0][0])
        self.assertEqual(a.page(1)[3], 7)

    def test_demo_and_cli(self):
        self.db.demo()
        self.assertEqual(self.rooms.page(1)[3], 5)
        with self.assertRaises(AppError):
            self.db.demo()
        output = io.StringIO()
        with patch('builtins.input', side_effect=['1', '4', '1', '0', '0', '0']), redirect_stdout(output):
            Main(self.db).run()
        self.assertIn('Стеллажи помещения', output.getvalue())
        self.assertNotIn('room_id', output.getvalue())
        self.assertNotIn('rack_id', output.getvalue())


if __name__ == '__main__':
    unittest.main()
