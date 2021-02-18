import logging
import os
# Path Constants
from collections import namedtuple

import discord

BASE_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
TOKEN = os.path.join(BASE_DIR, 'token.dat')
DATABASE = os.path.join(BASE_DIR, 'database.db')
DATABASE_URI = f'sqlite:///{DATABASE}'

# Discord-related constants
GENERAL_COLOR = discord.Color(0x4a90e2)
ERROR_COLOR = discord.Color(0xFF4848)
SUCCESS_COLOR = discord.Color(0x73E560)

# Other constants
LOGGING_LEVEL = logging.DEBUG


# Emote references
class Emoji(object):
    """A constants class storing the IDs of various Emojis used by the bot."""
    UPVOTE = 810310002220859393
    DOWNVOTE = 810310019840213002


# Named Tuples
ReactionMarker = namedtuple("ReactionMarker", ["message", "user", "emoji"], defaults=[Emoji.UPVOTE])
