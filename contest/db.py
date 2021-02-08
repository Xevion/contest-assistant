import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

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

    @classmethod
    async def create(cls) -> 'ContestDatabase':
        """
        Constructs a ContestDatabase object connecting to the default database location with the proper connection settings.
        :return: A fully realized ContestDatabase object.
        """
        conn = await aiosqlite.connect(constants.DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        logger.info(f'Asynchronous SQLite3 connection made to ./{os.path.relpath(constants.DATABASE)}')
        db = ContestDatabase(conn)
        await db.setup()
        await conn.commit()
        logger.info('ContestDatabase instance created.')
        return db

    async def setup(self) -> None:
        """Sets up the tables for initial database creation"""
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name = ?;''', ['guild'])
            if await cur.fetchone() is None:
                await self.conn.execute('''CREATE TABLE IF NOT EXISTS guild
                                            (id INTEGER PRIMARY KEY,
                                            prefix TEXT DEFAULT '$',
                                            submission INTEGER NULLABLE)''')
                logger.info(f"'guild' table created.")

            await cur.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name = ?;''', ['submission'])
            if await cur.fetchone() is None:
                await self.conn.execute('''CREATE TABLE IF NOT EXISTS submission
                                            (id INTEGER PRIMARY KEY,
                                            user INTEGER,
                                            guild INTEGER,
                                            timestamp DATETIME)''')
                logger.info(f"'submission' table created.")
        finally:
            await cur.close()

    async def setup_guild(self, guild_id: int) -> None:
        """Sets up a guild in the database."""
        await self.conn.execute('''INSERT INTO guild (id) VALUES (?)''', [guild_id])
        await self.conn.commit()

    async def set_prefix(self, guild_id: int, new_prefix: str) -> None:
        """Updates the prefix for a specific guild in the database"""
        await self.conn.execute('''UPDATE guild SET prefix = ? WHERE id = ?''', [new_prefix, guild_id])
        await self.conn.commit()

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
            return (await cur.fetchone())[0]
        finally:
            await cur.close()

    async def get_submission_channel(self, guild_id: int) -> int:
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT submission FROM guild WHERE id = ?''', [guild_id])
            return (await cur.fetchone())[0]
        finally:
            await cur.close()

    async def set_submission_channel(self, guild_id: int, new_submission: int) -> None:
        """Updates the submission channel for a specific guild in the database"""
        await self.conn.execute('''UPDATE guild SET submission = ? WHERE id = ?''', [new_submission, guild_id])
        await self.conn.commit()

    async def teardown_guild(self, guild_id: int) -> None:
        """Removes a guild from the database while completing appropriate teardown actions."""
        await self.conn.execute('''DELETE FROM guild WHERE id = ?''', [guild_id])
        await self.conn.commit()

    async def get_submission(self, guild_id: int, user_id: int) -> Optional[int]:
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT id FROM submission WHERE guild = ? AND user = ?''', [guild_id, user_id])
            row = await cur.fetchone()
            if row is None:
                return None
            return row[0]
        finally:
            await cur.close()

    async def add_submission(self, submission_id: int, guild_id: int, user_id: int, timestamp: int = None) -> None:
        await self.conn.execute(
            '''INSERT INTO submission (id, user, guild, timestamp) VALUES (?, ?, ?, ?)''',
            [submission_id, user_id, guild_id, timestamp or datetime.utcnow().timestamp()]
        )
        await self.conn.commit()
