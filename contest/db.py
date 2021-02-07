import logging
import sqlite3

import aiosqlite

from contest import constants

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


class ContestDatabase(object):
    """
    A handler class for a SQLite3 database used by the bot with Async support.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn
        self.setup()

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

    async def setup(self) -> None:
        """Sets up the tables for initial database creation"""
        await self.conn.execute('''CREATE TABLE IF NOT EXISTS guild
                            (id INTEGER PRIMARY KEY,
                            prefix TEXT DEFAULT '$',
                            submission INTEGER NULLABLE)''')

    async def setup_guild(self, guild_id: int) -> None:
        """Sets up a guild in the database."""
        await self.conn.execute('''INSERT INTO guild (id) VALUES (?)''', [guild_id])

    async def set_prefix(self, guild_id: int, new_prefix: str) -> None:
        """Updates the prefix for a specific guild in the database"""
        await self.conn.execute('''UPDATE guild SET prefix = ? WHERE id = ?''', [new_prefix, guild_id])

    async def is_setup(self, guild_id: int) -> bool:
        """Checks whether the bot is setup to complete submission channel related commands."""
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT submission FROM guild WHERE id = ?''', [guild_id])
            t = await cur.fetchone()
            print(t)
            return t['submission']
        finally:
            await cur.close()

    async def get_prefix(self, guild_id: int) -> str:
        """Gets the prefix from a specific guild in the database."""
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT prefix FROM guild WHERE id = ?''', [guild_id])
            return (await cur.fetchone())['prefix']
        finally:
            await cur.close()
