import datetime
import enum
import functools
import logging
from typing import List, Optional, Union

import discord
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from bot import constants, exceptions, helpers

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)

Base = declarative_base()


# TODO: Setup and test basic automatic migration.


class PeriodStates(enum.Enum):
    """
    A enum representing the possible states of on-going period.

    READY: Initial starting of the period. Submission channel is locked, no messages or reactions allowed.
    SUBMISSIONS: Submission channel is open, no reactions, messages with images only.
    PAUSED: Submission channel is locked again, no messages nor reactions.
    VOTING: Submission channel is open to reactions (voting) only. Vote reactions are added at this stage by the bot.
    FINISHED: Submission channel is locked again and final results are tallied.
    """
    READY = 0
    SUBMISSIONS = 1
    PAUSED = 2
    VOTING = 3
    FINISHED = 4


class Guild(Base):
    """Represents a Discord Guild the bot is in."""
    __tablename__ = 'guild'

    id = Column(Integer, primary_key=True)  # Doubles as the ID this Guild has in Discord
    prefix = Column(Text, default='$')  # The command prefix used by this particular guild.
    submission_channel = Column(Integer, nullable=True)  # The channel being scanned for messages by this particular guild.

    current_period_id = Column(Integer, ForeignKey('period.id'), nullable=True)  # The period currently active for this guild.
    current_period = relationship("Period", foreign_keys=current_period_id)
    periods = relationship("Period", back_populates="guild", foreign_keys="Period.guild_id")  # All periods ever started inside this guild

    active = Column(Boolean, default=True)  # Whether or not the bot is active inside the given Guild. Used for better querying.
    joined = Column(DateTime, default=datetime.datetime.utcnow)  # The initial join time for this bot to a particular Discord.
    last_joined = Column(DateTime, default=datetime.datetime.utcnow)  # The last time the bot joined this server.


def check_not_finished(func):
    """
    Throws `FinishedPeriod` if the period has already completed, is inactive, or is in it's Finished State.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.state is PeriodStates.FINISHED: raise exceptions.FinishedPeriod(f"Period is in it's Finished state.")
        elif not self.active: raise exceptions.FinishedPeriod("Period is no longer active.")
        elif self.completed: raise exceptions.FinishedPeriod("Period is already completed.")
        func(self, *args, **kwargs)

    return wrapper


class Submission(Base):
    """Represents a Message the bot has seen and remembered as a valid active submission."""
    __tablename__ = 'submission'

    id = Column(Integer, primary_key=True)  # Doubles as the ID this Guild has in Discord
    user = Column(Integer)  # The ID of the user who submitted it.
    timestamp = Column(DateTime)  # When the Submission was posted
    votes = Column(Integer, default=0)

    period_id = Column(Integer, ForeignKey("period.id"))  # The id of the period this Submission relates to.
    period = relationship("Period", back_populates="submissions")  # The period this submission was made in.

    def increment(self) -> None:
        """Increase the number of votes by one."""
        self.votes += 1

    def decrement(self) -> None:
        """Decrease the number of votes by one."""
        self.votes -= 1

    async def verify(self, message: discord.Message, user: Optional[Union[discord.ClientUser, discord.User]] = None) -> bool:
        """Sets the number of votes for this Submission."""
        saw_user = False
        for reaction in message.reactions:
            # Check that it's a custom Emoji and that the Emoji is the expected Upvote emoji
            if helpers.is_upvote(reaction.emoji):
                # If a user was specified, look for him in the reactions
                if user is not None:
                    reacting_user: Union[discord.Member, discord.User]
                    async for reacting_user in reaction.users():
                        # Check if the user who reacted to this emoji is the user we are looking for
                        if reacting_user.id == user.id:
                            saw_user = True
                            break

                # Tally the number of votes
                votes = reaction.count - 1
                if votes != self.votes:
                    # Make a racket if we counted wrong or somehow missed reactions
                    logger.warning(f'True vote count was off for Submission {self.id} by {votes - self.votes}.')
                    self.votes = votes

        return saw_user


class Period(Base):
    """Represents a particular period of submissions and voting for a given"""
    __tablename__ = "period"

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey("guild.id"))  # The guild this period was created in.
    guild = relationship("Guild", back_populates="periods", foreign_keys=guild_id)
    submissions: List[Submission] = relationship("Submission",
                                                 back_populates="period")  # All the submissions submitted during this Period's active state.

    state = Column(Enum(PeriodStates), default=PeriodStates.READY)  # The current state of the period.
    active = Column(Boolean, default=True)  # Whether this Period is currently running. State will not necessarily be FINISHED.
    completed = Column(Boolean, default=False)  # Whether this Period was completed to the end, properly.

    # TODO: Add automatic duration based advancement logic and tracking columns.

    start_time = Column(DateTime, default=datetime.datetime.utcnow())  # When this period was created/started (Ready state).
    submissions_time = Column(DateTime, nullable=True)  # When this period switched to the Submissions state.
    paused_time = Column(DateTime, nullable=True)  # When this period switched to the Paused state.
    voting_time = Column(DateTime, nullable=True)  # When this period switched to the Voting state.
    finished_time = Column(DateTime, nullable=True)  # When this period switched to the Finished state.

    @check_not_finished
    def advance_state(self) -> PeriodStates:
        """
        Advances the current recorded state of this Period, recording timestamps as needed.
        """
        next_state = PeriodStates(self.state.value + 1)
        if self.state == PeriodStates.READY:
            self.submissions_time = datetime.datetime.utcnow()
        elif self.state == PeriodStates.SUBMISSIONS:
            self.paused_time = datetime.datetime.utcnow()
        elif self.state == PeriodStates.PAUSED:
            self.voting_time = datetime.datetime.utcnow()
        elif self.state == PeriodStates.VOTING:
            self.finished_time = datetime.datetime.utcnow()
            self.completed = True
            self.active = False

        self.state = next_state
        return next_state

    @check_not_finished
    def deactivate(self) -> None:
        """
        Deactivates the period, setting it as inactive.

        Use `advance_state` if you want to properly advance the state.
        """
        self.finished_time = datetime.datetime.utcnow()
        self.active = False
