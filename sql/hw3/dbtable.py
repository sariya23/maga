"""Базовый класс таблиц: безопасная подстановка ТОЛЬКО SQL-идентификаторов."""

from psycopg2 import sql


class DbTable:
    NAME = None

    def __init__(self, dbconn):
        self.dbconn = dbconn

    def table(self):
        return self.dbconn.table(self.NAME)

    def count(self, conditions=None, params=()):
        query = sql.SQL("SELECT count(*) AS total FROM {}").format(self.table())
        if conditions is not None:
            # Условие задаётся только константой в коде, НЕ пользовательской строкой.
            query += sql.SQL(" WHERE ") + conditions
        result = self.dbconn.read_one(query, params)
        return result["total"]
