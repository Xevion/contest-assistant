import datetime
import enum

from sqlalchemy import Text, Integer, Column, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

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
    submissions = relationship("Submission", back_populates="guild")
    period = Column(Integer, ForeignKey('period.id'))  # The
    active = Column(Boolean, default=True)  # Whether or not the bot is active inside the given Guild. Used for better querying.
    joined = Column(DateTime, default=datetime.datetime.utcnow)  # The initial join time for this bot to a particular Discord.
    last_joined = Column(DateTime, nullable=True)  # The last time the bot joined this server.


class Submission(Base):
    """Represents a Message the bot has seen and remembered as a valid active submission."""
    __tablename__ = 'submission'

    id = Column(Integer, primary_key=True)  # Doubles as the ID this Guild has in Discord
    user = Column(Integer)  # The ID of the user who submitted it.
    guild_id = Column(Integer, ForeignKey("guild.id"))  # The ID of the Guild this submission is in.
    guild = relationship("Guild", back_populates="guild")  # The database Guild this Submission relates to.
    timestamp = Column(DateTime)  # When the Submission was posted

    period_id = Column(Integer, ForeignKey("period.id"))  # The id of the period this Submission relates to.
    period = relationship("Period", back_populates="period")  # The period this submission was made in.


class Period(Base):
    """Represents a particular period of submissions and voting for a given"""
    __tablename__ = "period"

    id = Column(Integer, primary_key=True)
    state = Column(Enum(PeriodStates))  # The current state of the period.
    submissions = Column(JSON, nullable=True)  # A simple JSON array representing

    start_time = Column(DateTime, default=datetime.datetime.utcnow())  # When this period was created/started (Ready state).
    submissions_time = Column(DateTime, nullable=True)  # When this period switched to the Submissions state.
    paused_time = Column(DateTime, nullable=True)  # When this period switched to the Paused state.
    voting_time = Column(DateTime, nullable=True)  # When this period switched to the Voting state.
    finished_time = Column(DateTime, nullable=True)  # When this period switched to the Finished state.
