import datetime
import random

import pytest
from sqlalchemy.orm import Session, sessionmaker
from itertools import count
from bot.models import Guild, Submission, Period
from main import load_db

numbers = count()

@pytest.fixture(scope='class')
async def SessionClass():
    engine = load_db('sqlite:///')
    yield sessionmaker(bind=engine)
    engine.dispose()

class TestSubmissions:
    @pytest.fixture()
    async def session(self, SessionClass) -> Session:
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

    @pytest.mark.asyncio
    async def test_submission_base(self, session) -> None:
        period = Period(id=next(numbers))
        session.add(period)
        submission = Submission(id=next(numbers), user=next(numbers), timestamp=datetime.datetime.utcnow(), period=period)
        session.add(submission)


class TestGuilds:
    @pytest.fixture()
    async def session(self, SessionClass) -> Session:
        session = SessionClass()
        yield session
        session.commit()
        session.close()

    @pytest.mark.asyncio
    async def test_guild_base(session) -> None:
        guild = Guild(id=0)
        session.commit()
        for guild in session.query(Guild).all():
            print(guild)
        pass

    class TestPeriods:
        @pytest.fixture()
        async def session(self, SessionClass) -> Session:
            session = SessionClass()
            yield session
            session.commit()
            session.close()

        @pytest.mark.asyncio
        async def test_period_base(session) -> None:
            period = Period(id=1, guild_id=1)
            session.commit()
            pass
