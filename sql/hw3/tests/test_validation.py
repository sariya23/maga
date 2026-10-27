"""Юнит-тесты граничных условий. Не требуют работающего PostgreSQL."""

import unittest
from decimal import Decimal

from validation import (
    ValidationError, number, positive_int, validate_room, validate_rack,
)


VALID_ROOM = dict(
    name="  Склад 'Оскар'; DROP TABLE rooms; -- ",
    usable_volume="200,000", temperature_min="-20", temperature_max="24.50",
    humidity_min="30", humidity_max="70",
)
VALID_RACK = dict(
    rack_number="10", storage_places="7", place_height="1.5",
    place_width="0.8", place_length="1", max_total_load="450.5",
)


class TestValidation(unittest.TestCase):
    def test_valid_room_with_commas_and_sql_metacharacters(self):
        actual = validate_room(VALID_ROOM)
        self.assertEqual(actual["usable_volume"], Decimal("200.000"))
        self.assertIn("DROP TABLE", actual["name"])  # имя — обычные данные, не SQL

    def test_empty_name(self):
        with self.assertRaises(ValidationError):
            validate_room({**VALID_ROOM, "name": " \t "})

    def test_freezing_point(self):
        self.assertEqual(number("-273.15", "T", 5, 2, lower="-273.15"), Decimal("-273.15"))
        with self.assertRaises(ValidationError):
            validate_room({**VALID_ROOM, "temperature_min": "-273.16"})

    def test_temperature_order(self):
        with self.assertRaisesRegex(ValidationError, "температура"):
            validate_room({**VALID_ROOM, "temperature_min": "50", "temperature_max": "10"})

    def test_humidity_boundaries(self):
        with self.assertRaises(ValidationError):
            validate_room({**VALID_ROOM, "humidity_max": "100.01"})
        with self.assertRaises(ValidationError):
            validate_room({**VALID_ROOM, "humidity_min": "-1"})
        with self.assertRaises(ValidationError):
            validate_room({**VALID_ROOM, "humidity_min": "99", "humidity_max": "98"})

    def test_negative_zero_and_precision(self):
        for value in ("-1", "0", "1.1234", "100000000000", "NaN", "Inf", "2e4", "1.2.3"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_room({**VALID_ROOM, "usable_volume": value})

    def test_valid_rack(self):
        parsed = validate_rack(VALID_RACK)
        self.assertEqual(parsed["rack_number"], 10)
        self.assertEqual(parsed["place_width"], Decimal("0.8"))

    def test_rack_invalid_integer(self):
        for value in ("0", "-1", "1.1", "2147483648", "anything", "0;DELETE", "9" * 10000, "0" * 10000):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                positive_int(value, "номер")

    def test_rack_dimension_precision(self):
        for value in ("0", "-0.001", "10000000", "0.0001"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_rack({**VALID_RACK, "place_height": value})

    def test_max_numeric_bounds(self):
        self.assertEqual(
            number("99999999999.999", "м", 14, 3, strictly_positive=True),
            Decimal("99999999999.999"),
        )
        with self.assertRaises(ValidationError):
            number("100000000000.000", "м", 14, 3)


if __name__ == "__main__":
    unittest.main()
