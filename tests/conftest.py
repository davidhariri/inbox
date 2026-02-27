import pytest

from inbox import db


@pytest.fixture
async def conn():
    """Fresh in-memory database for each test."""
    connection = await db.get_db(":memory:")
    # Mark setup as complete so tools work without auth flow
    await db.set_setting(connection, "setup_complete", "true")
    yield connection
    await connection.close()
