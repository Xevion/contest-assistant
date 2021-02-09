import logging
import os
import sqlite3
from collections import namedtuple
from datetime import datetime
from typing import Optional, List

import aiosqlite

from contest import constants

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)

Guild = namedtuple('Guild', ['id', 'prefix', 'submission', 'period'])
Submission = namedtuple('Submission', ['id', 'user', 'guild', 'timestamp'])
Period = namedtuple('Period', ['id', 'guild', 'current_state', 'started_at', 'voting_at', 'finished_at', ''])


class ContestDatabase(object):
    """
    A handler class for a SQLite3 database used by the bot with Async support.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    @classmethod
    async def create(cls, dest: str = constants.DATABASE) -> 'ContestDatabase':
        """
        Constructs a ContestDatabase object connecting to the default database location with the proper connection settings.
        :return: A fully realized ContestDatabase object.
        """

        conn = await aiosqlite.connect(dest, detect_types=sqlite3.PARSE_DECLTYPES)
        if dest.startswith(':memory:'):
            logger.info('Asynchronous SQLite3 connection started in memory.')
        else:
            logger.info(f'Asynchronous SQLite3 connection made to ./{os.path.relpath(constants.DATABASE)}')

        db = ContestDatabase(conn)
        await db.setup()
        await conn.commit()

        logger.info('ContestDatabase instance created, database setup.')

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
                                            submission INTEGER NULLABLE,
                                            period INTEGER)''')
                logger.info(f"'guild' table created.")

            await cur.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name = ?;''', ['submission'])
            if await cur.fetchone() is None:
                await self.conn.execute('''CREATE TABLE IF NOT EXISTS submission
                                            (id INTEGER PRIMARY KEY,
                                            user INTEGER,
                                            guild INTEGER,
                                            timestamp DATETIME)''')
                logger.info(f"'submission' table created.")

            await cur.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name = ?;''', ['period'])
            if await cur.fetchone() is None:
                await self.conn.execute('''CREATE TABLE IF NOT EXISTS period
                                            (id INTEGER PRIMARY KEY,
                                            guild INTEGER,
                                            current_state INTEGER,
                                            started_at TIMESTAMP,
                                            voting_at TIMESTAMP DEFAULT NULL,
                                            finished_at TIMESTAMP DEFAULT NULL)''')
                logger.info(f"'period' table created.")

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

    async def get_submission(self, guild_id: int, user_id: int) -> Optional[Submission]:
        """Retrieves a row from the submission table by the associated unique Guild ID and User ID"""
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT * FROM submission WHERE guild = ? AND user = ?''', [guild_id, user_id])
            row = await cur.fetchone()
            return None if row is None else Submission._make(row)
        finally:
            await cur.close()

    async def get_guild(self, guild_id: int) -> Optional[Guild]:
        """Retrieves a row from the Guild table by the Guild ID"""
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT * FROM guild WHERE id = ?''', [guild_id])
            row = await cur.fetchone()
            return None if row is None else Guild._make(row)
        finally:
            await cur.close()

    async def get_period(self, period_id) -> Optional[Period]:
        cur = await self.conn.cursor()
        try:
            await cur.execute('''SELECT * FROM period WHERE id = ?''', [period_id])
            row = await cur.fetchone()
            return None if row is None else Period._make(row)
        finally:
            await cur.close()

    async def get_current_period(self, guild_id: int) -> Optional[Period]:
        """Retrieves a row from the Guild table by the Guild ID"""
        cur = await self.conn.cursor()
        try:
            guild = await self.get_guild(guild_id)
            if guild is None:
                logger.debug(f'Guild {guild_id} does not exist.')
                return None

            if guild.period is not None:
                return await self.get_period(guild.period)
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

    async def add_submission(self, submission_id: int, guild_id: int, user_id: int, timestamp: int = None) -> None:
        await self.conn.execute(
            '''INSERT INTO submission (id, user, guild, timestamp) VALUES (?, ?, ?, ?)''',
            [submission_id, user_id, guild_id, timestamp or datetime.utcnow().timestamp()]
        )
        await self.conn.commit()

    @staticmethod
    async def generate_insert_query(table: str, columns: List[str]) -> str:
        return f'''INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})'''

    async def new_period(self, period: Period) -> None:
        """Given a period, adds the period to the table and updates the associated guild."""
        cur = await self.conn.cursor()
        try:
            # Ensure the associated guild exists
            if period.guild is None:
                return logger.error(f'Period {period} did not include a guild to associate with.')

            guild = await self.get_guild(period.guild)
            if guild is None:
                return logger.error(f'Specified guild {period.guild} does not exist.')

            # Add the period to the table
            items = filter(lambda item: item[1] is not None, period._asdict().items())
            columns, values = zip(*items)
            query = await self.generate_insert_query('period', list(columns))
            logger.debug(f'Generated Insert Query: {query}')
            await cur.execute(query, values)
            await self.conn.commit()

            # Update the associated guild's period
            await cur.execute('''UPDATE guild SET period = ? WHERE id = ?''', [cur.lastrowid, period.guild])
            await self.conn.commit()
        finally:
            await cur.close()

    async def update_period(self, ):
