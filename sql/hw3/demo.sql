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

