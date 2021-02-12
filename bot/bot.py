import logging
from typing import Optional

import discord
from discord.ext import commands

from bot import constants
from bot.db import ContestDatabase

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


async def fetch_prefix(bot: 'ContestBot', message: discord.Message):
    """Fetches the prefix used by the relevant guild."""
    user_id = bot.user.id
    base = [f'<@!{user_id}> ', f'<@{user_id}> ']

    if message.guild:
        if bot.db is not None:
            base.append(await bot.db.get_prefix(message.guild.id))
    return base


class ContestBot(commands.Bot):
    def __init__(self, **options):
        self.db: Optional[ContestDatabase] = None
        super().__init__(fetch_prefix, **options)

    async def on_ready(self):
        if self.db is None:
            self.db = await ContestDatabase.create()
        logger.info('Bot is now ready and connected to Discord.')
        guild_count = len(self.guilds)
        logger.info(
            f'Connected as {self.user.name}#{self.user.discriminator} to {guild_count} guild{"s" if guild_count > 1 else ""}.')

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f'Added to new guild: {guild.name} ({guild.id})')
        await self.db.setup_guild(guild.id)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info(f'Removed from guild: {guild.name} ({guild.id})')
        await self.db.teardown_guild(guild.id)
