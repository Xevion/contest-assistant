class ContestException(Exception):
    """A exception directly related to the Contest Assistant bot."""
    pass


class FinishedPeriodException(ContestException):
    """A inactive period, or a period in it's final state cannot be advanced or further modified."""

    def __repr__(self) -> str:
        return 'Period is inactive.'


class DatabaseDoubleVoteException(ContestException):
    """
    The database was asked to increment a vote for a submission with a user ID that was already added.

    Companion to `DatabaseNoVoteException`
    """

    def __repr__(self) -> str:
        return 'You can\'t vote for a submission twice.'


class DatabaseNoVoteException(ContestException):
    """
    The database was asked to decrement a vote for a submission with a user ID that did not or no longer exists for the given submission.

    Companion to `DatabaseDoubleVoteException`
    """

    def __repr__(self) -> str:
        return 'You can\'t remove a vote that never or no longer exists'


class SelfVoteException(ContestException):
    """A user tried to vote on his own submission."""

    def __repr__(self) -> str:
        return 'You can\'t vote on your own submission. Please choose another post.'
