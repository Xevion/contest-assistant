import logging
from contextlib import contextmanager
from datetime import datetime
from typing import ContextManager, List, Optional, Tuple

import discord
from discord.ext import commands
# noinspection PyProtectedMember
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from bot import constants
from bot.models import Guild, Period, Submission

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


class ContestBot(commands.Bot):
    def __init__(self, engine: Engine, **options):
        super().__init__(self.fetch_prefix, **options)

        self.engine = engine
        self.Session = sessionmaker(bind=engine)

        self.expected_msg_deletions: List[int] = []
        self.expected_react_deletions: List[Tuple[int, int]] = []

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
                guild: Guild = session.query(Guild).get(message.guild.id)
                base.append(guild.prefix)
        return base

    async def on_ready(self):
        """Communicate that the bot is online now."""
        logger.info('Bot is now ready and connected to Discord.')
        guild_count = len(self.guilds)
        logger.info(f'Connected as {self.user.name}#{self.user.discriminator} to {guild_count} guild{"s" if guild_count > 1 else ""}.')

        with self.get_session() as session:
            for guild in self.guilds:
                _guild: Guild = session.query(Guild).get(guild.id)
                if _guild is None:
                    logger.warning(
                            f'Guild {guild.name} ({guild.id}) was not inside database on ready. Bot was disconnected or did not add it properly...')
                    session.add(Guild(id=guild.id))

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handles adding or reactivating a Guild in the database."""
        logger.info(f'Added to new guild: {guild.name} ({guild.id})')

        with self.get_session() as session:
            _guild: Guild = session.query(Guild).get(guild.id)
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
            _guild: Guild = session.query(Guild).filter_by(active=True, id=guild.id).first()
            _guild.active = False

            # Shut down any current running Period objects if possible.
            period: Period = _guild.current_period
            if period is not None and period.active:
                period.deactivate()

    async def add_voting_reactions(self, channel: discord.TextChannel, submissions: Optional[List[Submission]] = None) -> None:
        """Adds reactions to all valid submissions in the given channel."""
        if submissions is None:
            with self.get_session() as session:
                period: Period = session.query(Guild).get(channel.guild.id).current_period
                if period is None:
                    logger.error('No valid submissions - current period is not set for the Guild this channel belongs to.')
                    return
                else:
                    submissions = period.submissions

        if len(submissions) == 0:
            logger.warning('Attempted to add voting reactions to submissions, but none were given or could be found.')
            return
        else:
            for submission in submissions:
                message: discord.PartialMessage = channel.get_partial_message(submission.id)
                await message.add_reaction(self.get_emoji(constants.Emoji.UPVOTE))

    def get_message(self, channel_id: int, message_id: int) -> discord.PartialMessage:
        """Get a PartialMessage object given raw integer IDs."""
        channel: discord.TextChannel = self.get_channel(channel_id)
        return channel.get_partial_message(message_id)

    async def fetch_message(self, channel_id: int, message_id: int) -> discord.Message:
        """Fetch a full Message object given raw integer IDs."""
        channel: discord.TextChannel = self.get_channel(channel_id)
        return await channel.fetch_message(message_id)

    @staticmethod
    async def reject(message: discord.Message, warning: str, delete_delay: int = 1, warning_duration: int = 5) -> None:
        """Send a warning message and delete the message, then the warning"""
        if delete_delay < 0:
            await message.delete(delay=delete_delay)
        warning = await message.channel.send(warning)
        if warning_duration < 0:
            await warning.delete(delay=warning_duration)
