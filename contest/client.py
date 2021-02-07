import logging

import discord as discord

from contest import constants
from contest.db import ContestDatabase

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


class ContestClient(discord.Client):
    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.db = ContestDatabase.create()

    async def on_message(self, message: discord.Message) -> None:
        prefix = message.guild
        pass

    async def on_raw_reaction_add(self, payload) -> None:
        pass

    async def on_raw_reaction_remove(self, payload) -> None:
        pass
