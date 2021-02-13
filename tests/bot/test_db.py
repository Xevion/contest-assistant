import pytest

from bot.db import ContestDatabase, tables


@pytest.fixture()
async def db() -> ContestDatabase:
    db = await ContestDatabase.create(':memory:')
    yield db
    await db.conn.close()


@pytest.mark.asyncio
async def test_table_setup(db) -> None:
    """Test that all tables were setup by the database."""
    cur = await db.conn.cursor()
    try:
        for table_namedtuple in tables:
            await cur.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name = ?;''',
                              [table_namedtuple.__name__.lower()])
            rows = list(await cur.fetchall())
            assert len(rows) == 1
    finally:
        await cur.close()


@pytest.mark.asyncio
async def test_guild_setup(db) -> None:
    await db.setup_guild(0)
    guild = await db.get_guild(0)
    assert guild is not None
    assert guild.submission is None

    assert await db.get_guild(1) is None


@pytest.mark.asyncio
async def test_update(db) -> None:
    pass


@pytest.mark.asyncio
async def test_generate_update_query(db) -> None:
    pass


@pytest.mark.asyncio
async def test_insert(db) -> None:
    """Test automatic namedtuple query"""
    pass


@pytest.mark.asyncio
async def test_generate_insert_query(db) -> None:
    """Test INSERT query generation."""
    pass


@pytest.mark.asyncio
async def test_submissions(db) -> None:
    """Test all submission related helper functions."""
    pass


@pytest.mark.asyncio
async def test_guilds(db) -> None:
    """Test all guild related helper functions"""
    pass


@pytest.mark.asyncio
async def test_periods(db) -> None:
    """Test all period related helper functions."""
    pass
