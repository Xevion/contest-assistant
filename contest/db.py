import sqlite3

import aiosqlite

from contest import constants


class ContestDatabase(object):
    """
    A handler class for a SQLite3 database used by the bot with Async support.
    """
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.db = conn

    @classmethod
    async def create(cls) -> 'ContestDatabase':
        """
        Constructs a ContestDatabase object connecting to the default database location with the proper connection settings.
        :return: A fully realized ContestDatabase object.
        """
        conn = await aiosqlite.connect(constants.DATABASE, detect_types=sqlite3.PARSE_DELCTYPES)
        db = ContestDatabase(conn)
        await conn.commit()
        return db

    async def is_setup(self):
        pass
