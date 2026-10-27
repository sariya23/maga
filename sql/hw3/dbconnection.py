"""Соединение с PostgreSQL; транзакции откатываются при любой ошибке."""

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql


class DbConnection:
    def __init__(self, config):
        self.schema = config.schema
        self.conn = psycopg2.connect(
            dbname=config.dbname, user=config.user, password=config.password,
            host=config.host, port=config.port, connect_timeout=5,
        )

    def table(self, name):
        """Имена схемы и таблицы экранируются средствами psycopg2."""
        return sql.Identifier(self.schema, name)

    def write(self, query, parameters=(), returning=False):
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, parameters)
                if returning:
                    return cursor.fetchone()
                return cursor.rowcount

    def read_one(self, query, parameters=()):
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchone()

    def read_all(self, query, parameters=()):
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchall()

    def close(self):
        self.conn.close()
