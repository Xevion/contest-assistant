import logging
import os

# Path Constants
from collections import namedtuple

BASE_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
TOKEN = os.path.join(BASE_DIR, 'token.dat')
DATABASE = os.path.join(BASE_DIR, 'database.db')
DATABASE_URI = f'sqlite:///{DATABASE}'

# Other constants
LOGGING_LEVEL = logging.DEBUG


# Emote references
class Emoji(object):
    """A constants class storing the IDs of various Emojis used by the bot."""
    UPVOTE = 810310002220859393
    DOWNVOTE = 810310019840213002


# Named Tuples
ReactionMarker = namedtuple("ReactionMarker", ["message", "user", "emoji"], defaults=[Emoji.UPVOTE])
