import datetime
from itertools import count

import pytest
from sqlalchemy.orm import Session, sessionmaker

from bot.models import Guild, Period, Submission
from main import load_db

numbers = count()


@pytest.fixture(scope='class')
def SessionClass():
    engine = load_db('sqlite:///')
    yield sessionmaker(bind=engine)
    engine.dispose()


class TestDatabase(object):
    @pytest.fixture()
    def session(self, SessionClass) -> Session:
        session = SessionClass()
        yield session
        session.commit()
        session.close()

    @pytest.fixture()
    def guild(self, session) -> Guild:
        guild = Guild(id=next(numbers), submission_channel=next(numbers))
        session.add(guild)
        session.commit()
        yield guild
        session.delete(guild)
        session.close()

    @pytest.fixture()
    def period(self, session: Session, guild: Guild):
        period = Period(id=next(numbers), guild=guild)
        session.add(period)
        session.commit()
        yield period
        session.delete(period)
        session.close()

    @pytest.fixture()
    def submission(self, session: Session, period: Period) -> Submission:
        submission = Submission(id=next(numbers), user=next(numbers), timestamp=datetime.datetime.utcnow(), period=period)
        session.add(submission)
        session.commit()
        yield submission
        session.delete(submission)
        session.close()


@pytest.mark.usefixtures("session", "guild", "submission", "period")
class TestSubmissions(TestDatabase):
    def test_submission_base(self, session) -> None:
        period = Period(id=next(numbers))
        session.add(period)
        submission = Submission(id=next(numbers), user=next(numbers), timestamp=datetime.datetime.utcnow(), period=period)
        session.add(submission)


@pytest.mark.usefixtures("session", "guild", "submission", "period")
class TestGuilds(TestDatabase):
    def test_guild_base(self, session: Session, guild: Guild) -> None:
        for guild in session.query(Guild).all():
            print(guild)
        pass


@pytest.mark.usefixtures("session", "guild", "submission", "period")
class TestPeriods(TestDatabase):
    @pytest.fixture()
    def session(self, SessionClass) -> Session:
        session = SessionClass()
        yield session
        session.commit()
        session.close()

    def test_period_base(self, session: SessionClass, period: Period) -> None:
        session.commit()
        pass
