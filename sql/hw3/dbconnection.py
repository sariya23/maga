from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor


class AppError(Exception):
    """Безопасное для пользователя описание ошибки."""


def database_message(error):
    code = error.pgcode or ''
    if code == '23505':
        return 'В этом помещении уже есть стеллаж с таким номером. Укажите другой номер.'
    if code == '23503':
        return ('Операция невозможна: запись связана с другими объектами. '
                'Перед удалением помещения удалите его стеллажи; если помещение уже удалено, вернитесь к списку.')
    if code.startswith('22') or code in ('23502', '23514'):
        return 'Данные не соответствуют допустимым значениям. Проверьте числа и диапазоны.'
    if code in ('40001', '40P01', '55P03', '57014'):
        return 'База занята или операция заняла слишком много времени. Повторите действие.'
    if code == '42501':
        return 'Недостаточно прав для работы с базой. Проверьте права пользователя в настройках.'
    if code in ('42P01', '3F000', '42703'):
        return 'Структура базы не соответствует проекту. Проверьте схему warehouse_hw3 и инициализацию.'
    if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)) or code.startswith('08'):
        return ('Нет связи с PostgreSQL. Проверьте сервер и настройки подключения. '
                'Если связь пропала при сохранении, обновите список перед повтором: результат операции неизвестен.')
    return 'База не смогла выполнить действие. Проверьте настройки и доступность PostgreSQL.'


class DbConnection:
    def __init__(self, config):
        self.config = config
        self.conn = None

    def run(self, action):
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(**self.config.connection)
            with self.conn:
                with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute('SET LOCAL search_path TO warehouse_hw3')
                    return action(cursor)
        except psycopg2.Error as error:
            self.close()
            raise AppError(database_message(error)) from None

    def initialize(self):
        script = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
        self.run(lambda cursor: cursor.execute(script))

    def demo(self):
        def insert(cursor):
            cursor.execute('LOCK TABLE rooms, racks IN EXCLUSIVE MODE')
            cursor.execute('SELECT EXISTS (SELECT 1 FROM rooms) AS populated')
            if cursor.fetchone()['populated']:
                raise AppError('Примеры добавляются только в пустую базу, чтобы не создавать дубликаты.')
            cursor.execute(Path(__file__).with_name('demo.sql').read_text(encoding='utf-8'))
        self.run(insert)

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
