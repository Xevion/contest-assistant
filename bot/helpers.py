from typing import Union

import discord

from bot import constants


def is_upvote(emoji: Union[discord.Emoji, discord.PartialEmoji, str]) -> bool:
    """Helper function for checking if the emoji returned is the upvote emoji the bot looks for."""
    if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
        if emoji.id == constants.Emoji.UPVOTE:
            return True
    return False
