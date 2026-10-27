-- Жуков Никита Романович, вариант 4.
-- Таблицы из ранее выполненного ДЗ. Создавать в выбранной БД PostgreSQL.
-- Не запускайте полный warehouse_homework_full.sql: в этой работе нужны только 2 таблицы.
CREATE TABLE IF NOT EXISTS public.rooms (
    room_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    usable_volume NUMERIC(14, 3) NOT NULL CHECK (usable_volume > 0),
    temperature_min NUMERIC(5, 2) NOT NULL,
    temperature_max NUMERIC(5, 2) NOT NULL,
    humidity_min NUMERIC(5, 2) NOT NULL,
    humidity_max NUMERIC(5, 2) NOT NULL,
    CONSTRAINT rooms_temperature_check CHECK (
        temperature_min >= -273.15 AND temperature_min <= temperature_max
    ),
    CONSTRAINT rooms_humidity_check CHECK (
        humidity_min >= 0 AND humidity_max <= 100 AND humidity_min <= humidity_max
    )
);
CREATE TABLE IF NOT EXISTS public.racks (
    rack_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rack_number INTEGER NOT NULL CHECK (rack_number > 0),
    room_id BIGINT NOT NULL REFERENCES public.rooms (room_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    storage_places INTEGER NOT NULL CHECK (storage_places > 0),
    place_height NUMERIC(10, 3) NOT NULL CHECK (place_height > 0),
    place_width NUMERIC(10, 3) NOT NULL CHECK (place_width > 0),
    place_length NUMERIC(10, 3) NOT NULL CHECK (place_length > 0),
    max_total_load NUMERIC(14, 3) NOT NULL CHECK (max_total_load > 0),
    CONSTRAINT racks_room_number_unique UNIQUE (room_id, rack_number)
);
