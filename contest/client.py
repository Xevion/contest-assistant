import logging
import re
from typing import Optional

import discord as discord

from contest import constants
from contest.db import ContestDatabase

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


class ContestClient(discord.Client):
    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.db: Optional[ContestDatabase] = None

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f'Added to new guild: {guild.name} ({guild.id})')
        await self.db.setup_guild(guild.id)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info(f'Removed from guild: {guild.name} ({guild.id})')
        await self.db.teardown_guild(guild.id)

    async def on_ready(self):
        await self.wait_until_ready()
        logger.info('Bot is now ready and connected to Discord.')
        guild_count = len(self.guilds)
        logger.info(
            f'Connected as {self.user.name}#{self.user.discriminator} to {guild_count} guild{"s" if guild_count > 1 else ""}.')
        self.db = await ContestDatabase.create()

    async def on_message(self, message: discord.Message) -> None:
        # Ignore self + bots
        if message.author == self.user or message.author.bot:
            return

        # Compile a regex made for parsing commands
        prefix = await self.db.get_prefix(message.guild.id)
        if message.content.startswith(prefix) and len(message.content) > 1:
            split = message.content[1:].split()
            command = split[0]
            args = split[1:]

            await message.channel.send(content=f'{command} {args}')


    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        pass

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        pass

    async def on_raw_reaction_clear(self, payload: discord.RawReactionActionEvent) -> None:
        pass

    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent) -> None:
        pass
