import datetime
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from bot.exceptions import FinishedPeriod

Base = declarative_base()


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

    current_period = Column(Integer, ForeignKey('period.id'), nullable=True)  # The period currently active for this guild.
    all_periods = relationship("Period", back_populates="guild")  # All periods ever started inside this guild

    active = Column(Boolean, default=True)  # Whether or not the bot is active inside the given Guild. Used for better querying.
    joined = Column(DateTime, default=datetime.datetime.utcnow)  # The initial join time for this bot to a particular Discord.
    last_joined = Column(DateTime, nullable=True)  # The last time the bot joined this server.


class Submission(Base):
    """Represents a Message the bot has seen and remembered as a valid active submission."""
    __tablename__ = 'submission'

    id = Column(Integer, primary_key=True)  # Doubles as the ID this Guild has in Discord
    user = Column(Integer)  # The ID of the user who submitted it.
    period_id = Column(Integer, ForeignKey("period.id"))  # The id of the period this Submission relates to.
    period = relationship("Period", back_populates="period")  # The period this submission was made in.
    timestamp = Column(DateTime)  # When the Submission was posted


class Period(Base):
    """Represents a particular period of submissions and voting for a given"""
    __tablename__ = "period"

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey("guild.id"))  # The guild this period was created in.
    guild = relationship("Guild", back_populates="guild")

    state = Column(Enum(PeriodStates))  # The current state of the period.
    active = Column(Boolean, default=True)  # Whether this Period is currently running. State will not necessarily be FINISHED.
    completed = Column(Boolean, default=False)  # Whether this Period was completed to the end, properly.
    submissions = relationship("Submission", back_populates="period")  # All the submissions submitted during this Period's active state.

    start_time = Column(DateTime, default=datetime.datetime.utcnow())  # When this period was created/started (Ready state).
    submissions_time = Column(DateTime, nullable=True)  # When this period switched to the Submissions state.
    paused_time = Column(DateTime, nullable=True)  # When this period switched to the Paused state.
    voting_time = Column(DateTime, nullable=True)  # When this period switched to the Voting state.
    finished_time = Column(DateTime, nullable=True)  # When this period switched to the Finished state.

    def advance_state(self) -> PeriodStates:
        """
        Advances the current recorded state of this Period, recording timestamps as needed.

        Throws FinishedPeriod if the period has already completed.
        """
        if self.state is PeriodStates.FINISHED: raise FinishedPeriod(f"Period is in it's Finished state.")
        elif not self.active: raise FinishedPeriod("Period is no longer active.")

        next_state = PeriodStates(int(self.state) + 1)
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

        return next_state
