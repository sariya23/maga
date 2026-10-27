from hw3.dbtable import DbTable
from hw3.validation import RACK_FIELDS


class RacksTable(DbTable):
    table = 'racks'
    key = 'rack_id'
    fields = RACK_FIELDS
    order = ('rack_number', 'rack_id')

    def __init__(self, connection, room_id):
        super().__init__(connection, room_id)
