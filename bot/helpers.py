import datetime
from typing import Any, Generator, List, Union

import discord

from bot import constants


def is_upvote(emoji: Union[discord.Emoji, discord.PartialEmoji, str]) -> bool:
    """Helper function for checking if the emoji returned is the upvote emoji the bot looks for."""
    if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
        if emoji.id == constants.Emoji.UPVOTE:
            return True
    return False


def general_embed(title: str = '', message: str = '', color: discord.Color = constants.GENERAL_COLOR,
                  timestamp: bool = False) -> discord.Embed:
    """A generic mostly unstyled embed with a blue color."""
    return discord.Embed(title=title, description=message, timestamp=datetime.datetime.utcnow() if timestamp else discord.Embed.Empty,
                         color=color)


def error_embed(*args, **kwargs):
    """A generic embed with a light red color."""
    kwargs['color'] = constants.ERROR_COLOR
    return general_embed(*args, **kwargs)


def success_embed(*args, **kwargs):
    """A generic embed with a light green color."""
    kwargs['color'] = constants.SUCCESS_COLOR
    return general_embed(*args, **kwargs)


def ending_iterator(items: List[Any]) -> Generator[Any, None, None]:
    """A generator which iterates along the list until it reaches the end, where it continuously yields the final item forever."""
    index = 0
    length = len(items) - 1
    last = items[-1]
    while True:
        if index == length:
            yield last
        else:
            yield items[index]
            index += 1
