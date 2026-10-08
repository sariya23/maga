/*
Жуков Никита Романович, вариант 4

Задание 1
Описание предметной области
Описание хранящихся на складе товаров. Включает в себя: описание помещений, описание стеллажей, описание клиентов, описание товаров, хранящихся на стеллажах. Описание помещения состоит из: названия, полезного объёма, температурных и влажностных условий. Описание стеллажа состоит из: номера, указания помещения, в котором стеллаж находится, количества мест для хранения в стеллаже, высоты, ширины и длины одного места, максимальной суммарной нагрузки. Описание клиента состоит из: названия юридического лица и банковских реквизитов в виде большого текста. Описание товара, хранящегося на стеллажах, состоит из: высоты, ширины, длины, веса, даты поступления, номера договора, указания, от какого клиента поступил, даты окончания договора, температурных и влажностных условий хранения, указания стеллажа, и позиции размещения на нём, представляемой в виде целого номера.
На одном стеллаже могут храниться товары разных клиентов.

Задание 2
Выберите номера стеллажей, а также объём одного места и суммарный объём всех мест на каждом из них.
Выберите названия юр. лиц всех клиентов и количество их товаров на стеллажах.
*/

CREATE TABLE rooms
(
    room_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT           NOT NULL CHECK (length(btrim(name)) > 0),
    usable_volume   NUMERIC(14, 3) NOT NULL CHECK (usable_volume > 0),
    temperature_min NUMERIC(5, 2)  NOT NULL,
    temperature_max NUMERIC(5, 2)  NOT NULL,
    humidity_min    NUMERIC(5, 2)  NOT NULL,
    humidity_max    NUMERIC(5, 2)  NOT NULL,
    CONSTRAINT rooms_temperature_check CHECK (
        temperature_min >= -273.15 AND temperature_min <= temperature_max
        ),
    CONSTRAINT rooms_humidity_check CHECK (
        humidity_min >= 0 AND humidity_max <= 100
            AND humidity_min <= humidity_max
        )
);

CREATE TABLE racks
(
    rack_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rack_number    INTEGER        NOT NULL CHECK (rack_number > 0),
    room_id        BIGINT         NOT NULL REFERENCES rooms (room_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    storage_places INTEGER        NOT NULL CHECK (storage_places > 0),
    place_height   NUMERIC(10, 3) NOT NULL CHECK (place_height > 0),
    place_width    NUMERIC(10, 3) NOT NULL CHECK (place_width > 0),
    place_length   NUMERIC(10, 3) NOT NULL CHECK (place_length > 0),
    max_total_load NUMERIC(14, 3) NOT NULL CHECK (max_total_load > 0),
    CONSTRAINT racks_room_number_unique UNIQUE (room_id, rack_number)
);

CREATE TABLE clients
(
    client_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    legal_name   TEXT NOT NULL CHECK (length(btrim(legal_name)) > 0),
    bank_details TEXT NOT NULL CHECK (length(btrim(bank_details)) > 0)
);

CREATE TABLE goods
(
    good_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    height            NUMERIC(10, 3) NOT NULL CHECK (height > 0),
    width             NUMERIC(10, 3) NOT NULL CHECK (width > 0),
    length            NUMERIC(10, 3) NOT NULL CHECK (length > 0),
    weight            NUMERIC(14, 3) NOT NULL CHECK (weight > 0),
    arrival_date      DATE           NOT NULL DEFAULT CURRENT_DATE,
    contract_number   TEXT           NOT NULL CHECK (length(btrim(contract_number)) > 0),
    client_id         BIGINT         NOT NULL REFERENCES clients (client_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    contract_end_date DATE           NOT NULL,
    temperature_min   NUMERIC(5, 2)  NOT NULL,
    temperature_max   NUMERIC(5, 2)  NOT NULL,
    humidity_min      NUMERIC(5, 2)  NOT NULL,
    humidity_max      NUMERIC(5, 2)  NOT NULL,
    rack_id           BIGINT         NOT NULL REFERENCES racks (rack_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    position_number   INTEGER        NOT NULL CHECK (position_number > 0),
    CONSTRAINT goods_contract_dates_check CHECK (
        contract_end_date >= arrival_date
        ),
    CONSTRAINT goods_temperature_check CHECK (
        temperature_min >= -273.15 AND temperature_min <= temperature_max
        ),
    CONSTRAINT goods_humidity_check CHECK (
        humidity_min >= 0 AND humidity_max <= 100
            AND humidity_min <= humidity_max
        ),
    CONSTRAINT goods_rack_position_unique UNIQUE (rack_id, position_number)

);

-- Практическое занятие 2. Заполнение таблиц и выборки
-- Размеры в метрах, объёмы в м³, масса в кг.
-- Демонстрационные данные; банковские реквизиты вымышлены.

BEGIN;

INSERT INTO rooms (name, usable_volume, temperature_min, temperature_max, humidity_min, humidity_max)
VALUES
    ('Основной склад', 500.000, 15, 25, 30, 60),
    ('Склад электроники', 200.000, 18, 24, 35, 55),
    ('Склад текстиля', 300.000, 15, 25, 40, 60),
    ('Склад автозапчастей', 400.000, 10, 25, 30, 65),
    ('Архивный склад', 150.000, 16, 22, 40, 55);

INSERT INTO racks (rack_number, room_id, storage_places, place_height, place_width, place_length, max_total_load)
SELECT v.rack_number, r.room_id, v.storage_places, v.height, v.width, v.length, v.max_load
FROM (VALUES
    (101, 'Основной склад', 20, 1.0, 1.2, 0.8, 2000.0),
    (102, 'Склад электроники', 15, 0.6, 0.8, 0.6, 750.0),
    (103, 'Склад текстиля', 25, 0.8, 1.0, 0.7, 1250.0),
    (104, 'Склад автозапчастей', 12, 1.2, 1.2, 1.0, 3000.0),
    (105, 'Архивный склад', 30, 0.4, 0.8, 0.5, 900.0)
) AS v(rack_number, room_name, storage_places, height, width, length, max_load)
JOIN rooms r ON r.name = v.room_name;

INSERT INTO clients (legal_name, bank_details)
VALUES
    ('ООО Альфа Логистика', 'Банк: Учебный банк 1; счёт: TEST-001'),
    ('ООО ТехноСнаб', 'Банк: Учебный банк 2; счёт: TEST-002'),
    ('ООО ТекстильТорг', 'Банк: Учебный банк 3; счёт: TEST-003'),
    ('ООО АвтоКомплект', 'Банк: Учебный банк 4; счёт: TEST-004'),
    ('ООО ДокументСервис', 'Банк: Учебный банк 5; счёт: TEST-005');

INSERT INTO goods (
    height, width, length, weight, arrival_date, contract_number, client_id,
    contract_end_date, temperature_min, temperature_max, humidity_min, humidity_max,
    rack_id, position_number
)
SELECT
    v.height, v.width, v.length, v.weight, v.arrival_date::DATE,
    v.contract_number, c.client_id, v.contract_end_date::DATE,
    v.temperature_min, v.temperature_max, v.humidity_min, v.humidity_max,
    r.rack_id, v.position_number
FROM (VALUES
    (0.5, 0.6, 0.4, 20.0, '2026-09-01', 'D-001', 'ООО Альфа Логистика', '2027-09-01', 16, 24, 35, 55, 101, 1),
    (0.4, 0.5, 0.3, 15.0, '2026-09-02', 'D-002', 'ООО Альфа Логистика', '2027-09-02', 16, 24, 35, 55, 101, 2),
    (0.3, 0.4, 0.3, 5.0, '2026-09-03', 'D-003', 'ООО ТехноСнаб', '2027-09-03', 18, 22, 40, 50, 102, 1),
    (0.4, 0.5, 0.4, 8.0, '2026-09-04', 'D-004', 'ООО ТехноСнаб', '2027-09-04', 18, 22, 40, 50, 102, 2),
    (0.5, 0.6, 0.4, 12.0, '2026-09-05', 'D-005', 'ООО ТекстильТорг', '2027-09-05', 17, 23, 45, 55, 103, 1),
    (0.6, 0.7, 0.5, 18.0, '2026-09-06', 'D-006', 'ООО ТекстильТорг', '2027-09-06', 17, 23, 45, 55, 103, 2),
    (0.5, 0.6, 0.5, 35.0, '2026-09-07', 'D-007', 'ООО АвтоКомплект', '2027-09-07', 12, 24, 35, 60, 104, 1),
    (0.7, 0.8, 0.6, 45.0, '2026-09-08', 'D-008', 'ООО АвтоКомплект', '2027-09-08', 12, 24, 35, 60, 104, 2),
    (0.3, 0.4, 0.3, 6.0, '2026-09-09', 'D-009', 'ООО ДокументСервис', '2027-09-09', 17, 21, 42, 52, 105, 1),
    (0.3, 0.4, 0.3, 7.0, '2026-09-10', 'D-010', 'ООО ДокументСервис', '2027-09-10', 17, 21, 42, 52, 105, 2)
) AS v(