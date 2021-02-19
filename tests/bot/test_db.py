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


def test_submission_count_descriptor(session: Session) -> None:
    sub = Submission(id=1, user=1)
    session.add(sub)
    session.commit()

    assert sub.votes == []
    assert sub.count == 0

    sub.votes = [1, 2, 2, 3]
    assert sub.votes == [1, 2, 3]
    assert sub.count == 3


def test_advance_state(session: Session) -> None:
    guild = Guild(id=1)
    per1 = Period(id=1, guild=guild)
    session.add(per1)
    session.commit()

    assert per1.active
    assert not per1.completed
    assert per1.state == PeriodStates.READY
    per1.advance_state()
    assert per1.active
    assert not per1.completed
    assert per1.state == PeriodStates.SUBMISSIONS
    per1.advance_state()
    assert per1.active
    assert not per1.completed
    assert per1.state == PeriodStates.PAUSED
    per1.advance_state()
    assert per1.active
    assert not per1.completed
    assert per1.voting
    assert per1.state == PeriodStates.VOTING
    per1.advance_state()
    assert per1.state == PeriodStates.FINISHED
    assert not per1.active
    assert per1.completed

    with pytest.raises(exceptions.FinishedPeriodException):
        per1.deactivate()
    with pytest.raises(exceptions.FinishedPeriodException):
        per1.deactivate()

    per2 = Period(id=2, guild=guild)
    session.add(per2)
    session.commit()
    per2.advance_state()
    per2.advance_state()
    per2.deactivate()
    assert per2.state == PeriodStates.PAUSED
    assert not per2.voting
    assert not per2.active and not per2.completed


def test_submission_clear_other_votes(session: Session) -> None:
    guild = Guild(id=1)
    per = Period(id=1, guild=guild)
    sub1 = Submission(id=1, user=1, period=per)
    sub2 = Submission(id=2, user=2, period=per)
    sub3 = Submission(id=3, user=3, period=per)
    session.add_all([guild, per, sub1, sub2, sub3])
    session.commit()

    sub1.votes = [1, 2]
    sub2.votes = [1, 2, 3]
    sub3.votes = [2, 3]

    sub2.clear_other_votes(ignore=sub2.id, users=[1, 2], session=session)

    assert sub1.votes == []
    assert sub2.votes == [1, 2, 3]
    assert sub3.votes == [3]




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
