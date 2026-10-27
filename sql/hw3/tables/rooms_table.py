"""CRUD для помещений из ДЗ модуля 1."""

from psycopg2 import sql
from dbtable import DbTable


class RoomsTable(DbTable):
    NAME = "rooms"
    FIELDS = (
        "name", "usable_volume", "temperature_min", "temperature_max",
        "humidity_min", "humidity_max",
    )

    def create(self):
        # Все типы и CHECK взяты из warehouse_homework_full.sql (вариант 4).
        ddl = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
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
                    humidity_min >= 0 AND humidity_max <= 100
                    AND humidity_min <= humidity_max
                )
            )
        """).format(self.table())
        self.dbconn.write(ddl)

    def page(self, offset, limit):
        query = sql.SQL("""
            SELECT room_id, name, usable_volume, temperature_min,
                   temperature_max, humidity_min, humidity_max
              FROM {} ORDER BY room_id LIMIT %s OFFSET %s
        """).format(self.table())
        return self.dbconn.read_all(query, (limit, offset))

    def get(self, room_id):
        query = sql.SQL("SELECT * FROM {} WHERE room_id = %s").format(self.table())
        return self.dbconn.read_one(query, (room_id,))

    def insert_one(self, data):
        cols = sql.SQL(", ").join(map(sql.Identifier, self.FIELDS))
        vals = tuple(data[field] for field in self.FIELDS)
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING room_id").format(
            self.table(), cols, sql.SQL(", ").join([sql.Placeholder()] * len(vals))
        )
        return self.dbconn.write(query, vals, returning=True)["room_id"]

    def update_one(self, room_id, data):
        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(field)) for field in self.FIELDS
        )
        query = sql.SQL("UPDATE {} SET {} WHERE room_id = %s").format(self.table(), assignments)
        vals = tuple(data[field] for field in self.FIELDS) + (room_id,)
        return self.dbconn.write(query, vals)

    def delete_one(self, room_id):
        query = sql.SQL("DELETE FROM {} WHERE room_id = %s").format(self.table())
        return self.dbconn.write(query, (room_id,))
