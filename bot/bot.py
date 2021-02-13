import logging
from contextlib import contextmanager
from datetime import datetime
from typing import ContextManager

import discord
from discord.ext import commands
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from bot import constants
from bot.models import Guild, Period

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


class ContestBot(commands.Bot):
    def __init__(self, engine: Engine, **options):
        super().__init__(self.fetch_prefix, **options)

        self.engine = engine
        self.Session = sessionmaker(bind=engine)

    @contextmanager
    def get_session(self, autocommit=True, autoclose=True, rollback=True) -> ContextManager[Session]:
        """Provides automatic commit and closing of Session with exception rollback."""
        session = self.Session()
        try:
            yield session
            if autocommit: session.commit()
        except Exception:
            if rollback: session.rollback()
            raise
        finally:
            if autoclose: session.close()

    async def fetch_prefix(self, bot: 'ContestBot', message: discord.Message):
        """Fetches the prefix used by the relevant guild."""
        user_id = bot.user.id
        base = [f'<@!{user_id}> ', f'<@{user_id}> ']

        if message.guild:
            with self.get_session() as session:
                guild = session.query(Guild).filter_by(id=message.guild.id).first()
                base.append(guild.prefix)
        return base

    async def on_ready(self):
        logger.info('Bot is now ready and connected to Discord.')
        guild_count = len(self.guilds)
        logger.info(
            f'Connected as {self.user.name}#{self.user.discriminator} to {guild_count} guild{"s" if guild_count > 1 else ""}.')

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handles adding or reactivating a Guild in the database."""
        logger.info(f'Added to new guild: {guild.name} ({guild.id})')

        with self.get_session() as session:
            _guild: Guild = session.query(Guild).filter_by(active=False, id=guild.id).first()
            if _guild is None:
                session.add(Guild(id=guild.id))
            else:
                # Guild has been seen before. Update last_joined and set as active again.
                _guild.active = True
                _guild.last_joined = datetime.utcnow()

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Handles disabling the guild in the database, as well."""
        logger.info(f'Removed from guild: {guild.name} ({guild.id})')

        with self.get_session() as session:
            # Get the associated Guild and mark it as disabled.
            _guild = session.query(Guild).filter_by(active=True, id=guild.id).first()
            _guild.active = False

            # Shut down any current running Period objects if possible.
            period: Period = _guild.current_period
            if period is not None and period.active:
                period.deactivate()
