"""Валидация на стороне Python ДО выполнения SQL.

Соответствует точным ограничениям NUMERIC/INTEGER/CHECK из ДЗ варианта 4.
"""

import re
from decimal import Decimal, InvalidOperation


class ValidationError(ValueError):
    pass


NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?\Z")
INTEGER_RE = re.compile(r"\+?\d+\Z")


def name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Название помещения не может быть пустым.")
    if "\x00" in value:
        raise ValidationError("Название не может содержать нулевой символ.")
    return value.strip()


def number(value, label, precision, scale, lower=None, upper=None, strictly_positive=False):
    raw = str(value).strip().replace(",", ".")
    if not NUMBER_RE.fullmatch(raw):
        raise ValidationError(f"{label}: требуется обычное число (разделитель — точка или запятая).")
    integral, _, fraction = raw.lstrip("+-").partition(".")
    if len(integral.lstrip("0")) > precision - scale or len(fraction) > scale:
        raise ValidationError(f"{label}: максимум {precision - scale} цифр до и {scale} после запятой.")
    try:
        result = Decimal(raw)
    except InvalidOperation:
        raise ValidationError(f"{label}: неверный формат числа.") from None
    if strictly_positive and result <= 0:
        raise ValidationError(f"{label}: значение должно быть больше нуля.")
    if lower is not None and result < Decimal(str(lower)):
        raise ValidationError(f"{label}: минимум {lower}.")
    if upper is not None and result > Decimal(str(upper)):
        raise ValidationError(f"{label}: максимум {upper}.")
    return result


def positive_int(value, label):
    raw = str(value).strip()
    if not INTEGER_RE.fullmatch(raw):
        raise ValidationError(f"{label}: требуется целое положительное число.")
    # Ограничение длины ДО int(): Python 3.11+ иначе может выбросить ValueError
    # на строке из нескольких тысяч цифр. Нули слева не меняют значение.
    if len(raw) > 20 or len(raw.lstrip("+").lstrip("0")) > 10:
        raise ValidationError(f"{label}: число должно быть от 1 до 2147483647.")
    result = int(raw)
    if not 1 <= result <= 2_147_483_647:
        raise ValidationError(f"{label}: число должно быть от 1 до 2147483647.")
    return result


ROOM_FIELDS = (
    ("name", "Название помещения", lambda v: name(v)),
    ("usable_volume", "Полезный объём, м³", lambda v: number(v, "Полезный объём", 14, 3, strictly_positive=True)),
    ("temperature_min", "Минимальная температура, °C", lambda v: number(v, "Минимальная температура", 5, 2, lower="-273.15")),
    ("temperature_max", "Максимальная температура, °C", lambda v: number(v, "Максимальная температура", 5, 2, lower="-273.15")),
    ("humidity_min", "Минимальная влажность, %", lambda v: number(v, "Минимальная влажность", 5, 2, lower=0, upper=100)),
    ("humidity_max", "Максимальная влажность, %", lambda v: number(v, "Максимальная влажность", 5, 2, lower=0, upper=100)),
)

RACK_FIELDS = (
    ("rack_number", "Номер стеллажа", lambda v: positive_int(v, "Номер стеллажа")),
    ("storage_places", "Количество мест", lambda v: positive_int(v, "Количество мест")),
    ("place_height", "Высота места, м", lambda v: number(v, "Высота места", 10, 3, strictly_positive=True)),
    ("place_width", "Ширина места, м", lambda v: number(v, "Ширина места", 10, 3, strictly_positive=True)),
    ("place_length", "Длина места, м", lambda v: number(v, "Длина места", 10, 3, strictly_positive=True)),
    ("max_total_load", "Максимальная суммарная нагрузка, кг", lambda v: number(v, "Нагрузка", 14, 3, strictly_positive=True)),
)


def validate_room(data):
    result = {key: parse(data[key]) for key, _, parse in ROOM_FIELDS}
    if result["temperature_min"] > result["temperature_max"]:
        raise ValidationError("Минимальная температура не может быть выше максимальной.")
    if result["humidity_min"] > result["humidity_max"]:
        raise ValidationError("Минимальная влажность не может быть выше максимальной.")
    return result


def validate_rack(data):
    return {key: parse(data[key]) for key, _, parse in RACK_FIELDS}
