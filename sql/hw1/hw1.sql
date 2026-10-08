/*

Жуков Никита Романович, вариант 4

Описание предметной области

Описание хранящихся на складе товаров. Включает в себя: описание помещений, описание стеллажей, описание клиентов, описание товаров, хранящихся на стеллажах. Описание помещения состоит из: названия, полезного объёма, температурных и влажностных условий. Описание стеллажа состоит из: номера, указания помещения, в котором стеллаж находится, количества мест для хранения в стеллаже, высоты, ширины и длины одного места, максимальной суммарной нагрузки. Описание клиента состоит из: названия юридического лица и банковских реквизитов в виде большого текста. Описание товара, хранящегося на стеллажах, состоит из: высоты, ширины, длины, веса, даты поступления, номера договора, указания, от какого клиента поступил, даты окончания договора, температурных и влажностных условий хранения, указания стеллажа, и позиции размещения на нём, представляемой в виде целого номера.

На одном стеллаже могут храниться товары разных клиентов.

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