from hw3.dbtable import DbTable
from hw3.validation import ROOM_FIELDS


class RoomsTable(DbTable):
    table = 'rooms'
    key = 'room_id'
    fields = ROOM_FIELDS
    order = ('name', 'room_id')
