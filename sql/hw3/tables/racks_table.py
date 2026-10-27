"""Стеллажи конкретного помещения; ни один публичный метод не требует id от пользователя."""

from psycopg2 import sql
from dbtable import DbTable


class RacksTable(DbTable):
    NAME = "racks"
    FIELDS = (
        "rack_number", "storage_places", "place_height", "place_width",
        "place_length", "max_total_load",
    )

    def create(self):
        ddl = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                rack_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                rack_number INTEGER NOT NULL CHECK (rack_number > 0),
                room_id BIGINT NOT NULL REFERENCES {} (room_id)
                    ON DELETE RESTRICT ON UPDATE RESTRICT,
                storage_places INTEGER NOT NULL CHECK (storage_places > 0),
                place_height NUMERIC(10, 3) NOT NULL CHECK (place_height > 0),
                place_width NUMERIC(10, 3) NOT NULL CHECK (place_width > 0),
                place_length NUMERIC(10, 3) NOT NULL CHECK (place_length > 0),
                max_total_load NUMERIC(14, 3) NOT NULL CHECK (max_total_load > 0),
                CONSTRAINT racks_room_number_unique UNIQUE (room_id, rack_number)
            )
        """).format(self.table(), self.dbconn.table("rooms"))
        self.dbconn.write(ddl)

    def count_for_room(self, room_id):
        return self.count(sql.SQL("room_id = %s"), (room_id,))

    def page_for_room(self, room_id, offset, limit):
        query = sql.SQL("""
            SELECT rack_id, rack_number, room_id, storage_places,
                   place_height, place_width, place_length, max_total_load
              FROM {} WHERE room_id = %s
              ORDER BY rack_number, rack_id LIMIT %s OFFSET %s
        """).format(self.table())
        return self.dbconn.read_all(query, (room_id, limit, offset))

    def insert_one(self, room_id, data):
        fields = ("room_id",) + self.FIELDS
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING rack_id").format(
            self.table(),
            sql.SQL(", ").join(map(sql.Identifier, fields)),
            sql.SQL(", ").join([sql.Placeholder()] * len(fields)),
        )
        values = (room_id,) + tuple(data[field] for field in self.FIELDS)
        return self.dbconn.write(query, values, returning=True)["rack_id"]

    def update_one(self, rack_id, room_id, data):
        # Условие room_id не даёт изменять стеллаж из чужого помещения.
        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(field)) for field in self.FIELDS
        )
        query = sql.SQL("UPDATE {} SET {} WHERE rack_id = %s AND room_id = %s").format(
            self.table(), assignments
        )
        vals = tuple(data[field] for field in self.FIELDS) + (rack_id, room_id)
        return self.dbconn.write(query, vals)

    def delete_one(self, rack_id, room_id):
        query = sql.SQL("DELETE FROM {} WHERE rack_id = %s AND room_id = %s").format(self.table())
        return self.dbconn.write(query, (rack_id, room_id))
