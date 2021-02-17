import random
from itertools import count
from typing import Generator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from bot import exceptions
from bot.models import Guild, Period, PeriodStates, Submission
from main import load_db

numbers = count()


@pytest.fixture(scope='class')
def SessionClass():
    engine = load_db('sqlite:///')
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture(scope='function')
def session(SessionClass: sessionmaker):
    s: Session = SessionClass()
    try:
        yield s
    finally:
        s.close()


def test_submission_increment(session: Session):
    sub = Submission(id=1, user=1)
    session.bulk_save_objects([sub])
    session.commit()

    with pytest.raises(exceptions.SelfVoteException):
        sub.increment(1)
    sub.increment(2)
    assert sub.votes == [2]
    with pytest.raises(exceptions.DatabaseDoubleVoteException):
        sub.increment(2)


def test_submission_decrement(session: Session) -> None:
    sub = Submission(id=1, user=1)
    session.add(sub)
    session.commit()

    sub.votes = [1]
    sub.decrement(1)
    assert sub.votes == []
    with pytest.raises(exceptions.DatabaseNoVoteException):
        sub.decrement(1)


def test_advance_state(session: Session) -> None:
    guild = Guild(id=1)
    per = Period(id=1, guild=guild)
    session.add(per)
    session.commit()

    assert per.state == PeriodStates.READY
    per.advance_state()
    assert per.state == PeriodStates.SUBMISSIONS
    per.advance_state()
    assert per.state == PeriodStates.PAUSED
    per.advance_state()
    assert per.state == PeriodStates.VOTING
    per.advance_state()
    assert per.state == PeriodStates.FINISHED


@pytest.fixture()
def database(SessionClass: sessionmaker):
    session: Session = SessionClass()

    def users(user_ids) -> Generator[int, None, None]:
        index = 0
        random.shuffle(user_ids)
        while True:
            if index >= len(user_ids):
                random.shuffle(user_ids)
                index = 0
            yield user_ids[index]
            index += 1

    user_ids = [next(numbers) for _ in range(50)]
    guild = Guild(id=next(numbers), submission_channel=next(numbers))
    users = users(user_ids)

    for _ in range(3):
        for state in PeriodStates:
            period = Period(id=next(numbers), guild=guild)
            while period.active and period.state != state:
                period.advance_state()

            for _ in range(50):
                s = Submission(id=next(numbers), user=next(users), period=period)
                session.add(s)

            session.add(period)
    session.add(guild)

    session.commit()
    yield session
    session.close()


def test_database(database: Session) -> None:
    database.query(Guild).all()
    print(database.query(Period).all())
    print(database.query(Submission).all())
