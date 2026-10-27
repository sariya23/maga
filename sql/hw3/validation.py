import re
from decimal import Decimal


class ValidationError(ValueError):
    pass


def name(value):
    value = str(value).strip()
    if not value:
        raise ValidationError('Название не может быть пустым.')
    if any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValidationError('Название не должно содержать управляющие символы.')
    return value


def integer(value):
    value = str(value).strip()
    if not re.fullmatch(r'[0-9]{1,10}', value):
        raise ValidationError('Введите целое положительное число до 2147483647.')
    result = int(value)
    if not 1 <= result <= 2147483647:
        raise ValidationError('Число должно быть от 1 до 2147483647.')
    return result


def numeric(precision, scale, minimum=None, positive=False):
    def parse(value):
        value = str(value).strip().replace(',', '.')
        if len(value) > 100 or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', value):
            raise ValidationError('Введите обычное десятичное число (например, 12,5).')
        result = Decimal(value)
        if result.as_tuple().exponent < -scale:
            raise ValidationError(f'Допустимо не более {scale} знаков после запятой.')
        if abs(result) >= Decimal(10) ** (precision - scale):
            raise ValidationError(f'Допустимо не более {precision - scale} цифр до запятой.')
        if positive and result <= 0:
            raise ValidationError('Значение должно быть больше нуля.')
        if minimum is not None and result < Decimal(str(minimum)):
            raise ValidationError(f'Значение должно быть не меньше {minimum}.')
        return result
    return parse


ROOM_FIELDS = (
    ('name', 'Название помещения', name),
    ('usable_volume', 'Полезный объём, м³', numeric(14, 3, positive=True)),
    ('temperature_min', 'Минимальная температура, °C', numeric(5, 2, -273.15)),
    ('temperature_max', 'Максимальная температура, °C', numeric(5, 2, -273.15)),
    ('humidity_min', 'Минимальная влажность, %', numeric(5, 2, 0)),
    ('humidity_max', 'Максимальная влажность, %', numeric(5, 2, 0)),
)
RACK_FIELDS = (
    ('rack_number', 'Номер стеллажа (на складе)', integer),
    ('storage_places', 'Количество мест', integer),
    ('place_height', 'Высота места, м', numeric(10, 3, positive=True)),
    ('place_width', 'Ширина места, м', numeric(10, 3, positive=True)),
    ('place_length', 'Длина места, м', numeric(10, 3, positive=True)),
    ('max_total_load', 'Максимальная нагрузка, кг', numeric(14, 3, positive=True)),
)


def validate(fields, values):
    data = {key: parser(values[key]) for key, _, parser in fields}
    if fields == ROOM_FIELDS:
        if data['temperature_min'] > data['temperature_max']:
            raise ValidationError('Минимальная температура не может превышать максимальную.')
        if not data['humidity_min'] <= data['humidity_max'] <= 100:
            raise ValidationError('Влажность должна быть от 0 до 100%; минимум не больше максимума.')
    return data
