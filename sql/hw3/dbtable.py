from psycopg2 import sql
from hw3.dbconnection import AppError
from hw3.validation import validate


class DbTable:
    page_size = 5

    def __init__(self, connection, room_id=None):
        self.connection = connection
        self.room_id = room_id

    def scope(self):
        if self.room_id is None:
            return sql.SQL('TRUE'), []
        return sql.SQL('room_id = %s'), [self.room_id]

    def page(self, number):
        def select(cursor):
            where, params = self.scope()
            cursor.execute(sql.SQL('SELECT count(*) AS count FROM {} WHERE {}').format(
                sql.Identifier(self.table), where), params)
            count = cursor.fetchone()['count']
            pages = max(1, (count + self.page_size - 1) // self.page_size)
            current = max(1, min(number, pages))
            cursor.execute(sql.SQL('SELECT * FROM {} WHERE {} ORDER BY {} LIMIT %s OFFSET %s').format(
                sql.Identifier(self.table), where,
                sql.SQL(', ').join(map(sql.Identifier, self.order))),
                params + [self.page_size, (current - 1) * self.page_size])
            return cursor.fetchall(), current, pages, count
        return self.connection.run(select)

    def save(self, values, original=None):
        data = validate(self.fields, values)
        if self.room_id is not None:
            data['room_id'] = self.room_id
        def write(cursor):
            if original is None:
                cursor.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                    sql.Identifier(self.table),
                    sql.SQL(', ').join(map(sql.Identifier, data)),
                    sql.SQL(', ').join(sql.Placeholder() for _ in data)), list(data.values()))
            else:
                where, params = self.original_filter(original)
                cursor.execute(sql.SQL('UPDATE {} SET {} WHERE {}').format(
                    sql.Identifier(self.table),
                    sql.SQL(', ').join(sql.SQL('{} = %s').format(sql.Identifier(k)) for k in data),
                    where), list(data.values()) + params)
                if cursor.rowcount != 1:
                    raise AppError('Запись уже изменена или удалена. Обновите список и повторите действие.')
        self.connection.run(write)

    def original_filter(self, original):
        # Сравниваем показанную версию: чужие изменения не перезаписываются молча.
        where, params = self.scope()
        keys = [self.key] + [key for key, _, _ in self.fields]
        predicates = [sql.SQL('{} = %s').format(sql.Identifier(key)) for key in keys]
        return sql.SQL(' AND ').join([where] + predicates), params + [original[k] for k in keys]

    def delete(self, original):
        def remove(cursor):
            where, params = self.original_filter(original)
            cursor.execute(sql.SQL('DELETE FROM {} WHERE {}').format(sql.Identifier(self.table), where), params)
            if cursor.rowcount != 1:
                raise AppError('Запись уже изменена или удалена. Обновите список и повторите действие.')
        self.connection.run(remove)
