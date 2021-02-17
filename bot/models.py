import datetime
import enum
import functools
import itertools
import logging
from typing import Iterable, List, TYPE_CHECKING, Tuple, Union

import discord
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy_json import NestedMutableList

from bot import constants, exceptions, helpers
from bot.constants import ReactionMarker

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from bot.bot import ContestBot

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
        if self.state is PeriodStates.FINISHED: raise exceptions.FinishedPeriodException(f"Period is in it's Finished state.")
        elif not self.active: raise exceptions.FinishedPeriodException("Period is no longer active.")
        elif self.completed: raise exceptions.FinishedPeriodException("Period is already completed.")
        func(self, *args, **kwargs)

    return wrapper


class Submission(Base):
    """Represents a Message the bot has seen and remembered as a valid active submission."""
    __tablename__ = 'submission'

    id = Column(Integer, primary_key=True)  # Doubles as the ID this Guild has in Discord
    user = Column(Integer)  # The ID of the user who submitted it.
    timestamp = Column(DateTime)  # When the Submission was posted
    votes: List[int] = Column(NestedMutableList.as_mutable(JSON))  # A list of IDs correlating to users who voted on this submission.

    period_id = Column(Integer, ForeignKey("period.id"))  # The id of the period this Submission relates to.
    period = relationship("Period", back_populates="submissions")  # The period this submission was made in.

    def __init__(self, **kwds):
        # Adds default column behavior for Mutable JSON votes column
        kwds.setdefault("votes", [])
        super().__init__(**kwds)

    def __repr__(self) -> str:
        return 'Submission(id={id}, user={user}, period={period_id}, {votes})'.format(**self.__dict__)

    @property
    def count(self) -> int:
        """The number of votes cast for this submission."""
        return len(self.votes)

    def increment(self, user: int) -> None:
        """Increase the number of votes by one."""
        if user == self.user:
            raise exceptions.SelfVoteException()
        elif user in self.votes:
            raise exceptions.DatabaseDoubleVoteException()
        self.votes.append(user)

    def decrement(self, user: int) -> None:
        """Decrease the number of votes by one."""
        if user not in self.votes:
            raise exceptions.DatabaseNoVoteException()
        self.votes.remove(user)

    def clear_other_votes(self, ignore: Union[int, Iterable[int]], users: Union[int, Iterable[int]], session: 'Session') -> ReactionMarker:
        """
        Removes votes from all submissions in the database for a specific user.
        Returns a list of combination Message and User IDs

        :param ignore: The Submission ID(s) to ignore.
        :param users: The User ID(s) to clear.
        :param session: A SQLAlchemy session to use for querying.
        :return: A list of tuples containing a Message ID then User ID who voted for submissions other than the ones being ignored.
        """
        if isinstance(ignore, int): ignore = [ignore]
        if isinstance(users, int): users = [users]
        ignore, users = set(ignore), set(users)
        if len(ignore) == 0: logger.warning(f'Clearing ALL votes for user(s): {users}')
        if len(users) == 0: return []

        found: List[Tuple[int, int]] = []
        submissions = session.query(Submission).filter(Submission.id != self.id).all()
        for submission in submissions:
            # Ignore submissions in the ignore list
            if submission.id in ignore:
                continue

            # Find what users voted for this submission that we are clearing
            votes = set(submission.votes)
            same = votes.intersection(users)
            if len(same) > 0:
                continue

            # Remove votes from the submission by said users
            submission.votes = list(votes - same)

            # For each user we found that voted, return a tuple Message ID & User ID
            for shared_user in same:
                found.append(ReactionMarker(message=submission.id, user=shared_user))

        return found

    async def update(self, bot: 'ContestBot', message: discord.Message = None) -> None:
        """Updates the number of votes in the database by thoroughly evaluating the message."""
        saw_self, current, old = False, set(), set(self.votes)  # Votes currently on the message and votes only on the submission

        for reaction in message.reactions:
            if helpers.is_upvote(reaction.emoji):
                reacting_user: Union[discord.Member, discord.User]
                async for reacting_user in reaction.users():
                    # Check if this is our bot reacting
                    if reacting_user.id == bot.user.id:
                        saw_self = True
                    else:
                        current.add(reacting_user.id)

        to_add, to_remove, report = current - old, old - current, ''
        if len(to_add) > 0:
            report += f'Added: {", ".join(map(str, to_add))}'

            with bot.get_session() as session:
                channel: discord.TextChannel = message.channel

                # Iterate through each user who has added a reaction since the last check
                for user_id in to_add:
                    # Remove their votes in other submissions
                    reactions_to_clear = self.clear_other_votes(ignore=self.id, users=user_id, session=session)

                    # Then remove all upvote reactions from that user from other submission
                    for message_id, reaction_tuples in itertools.groupby(reactions_to_clear, lambda marker: marker.message):
                        message_to_clear: discord.Message = await channel.fetch_message(message_id)
                        reaction_marker: ReactionMarker

                        # Should only iterate once, but we'll ready it for multiple users
                        for reaction_marker in reaction_tuples:
                            await message_to_clear.remove_reaction(
                                    bot.get_emoji(constants.Emoji.UPVOTE),
                                    message.guild.get_member(reaction_marker.user)
                            )

        # Update the current list of votes
        self.votes = list(current)

        if len(to_remove) > 0:
            if report: report += ' '
            report += f'Removed: {", ".join(map(str, to_remove))}'
        if report: logger.debug(report)

        # If we never saw ourselves in the reaction, add the Upvote emoji
        if not saw_self:
            await message.add_reaction(constants.Emoji.UPVOTE)


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

    def __repr__(self) -> str:
        return 'Period(id={id}, guild={guild_id}, {state.name}, active={active})'.format(**self.__dict__)
