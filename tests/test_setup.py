import bcrypt

from inbox import db


async def test_setup_not_complete_initially(conn):
    # Undo the conftest default
    await db.set_setting(conn, "setup_complete", "false")
    assert not await db.is_setup_complete(conn)


async def test_setup_complete(conn):
    assert await db.is_setup_complete(conn)


async def test_secret_key_auto_generates(conn):
    key1 = await db.get_secret_key(conn)
    assert len(key1) == 64  # hex string of 32 bytes
    key2 = await db.get_secret_key(conn)
    assert key1 == key2  # Same key on second call


async def test_create_user(conn):
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    user = await db.create_user(conn, "test@example.com", hashed)
    assert user["email"] == "test@example.com"
    assert user["id"] is not None


async def test_get_user_by_email(conn):
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    await db.create_user(conn, "test@example.com", hashed)

    user = await db.get_user_by_email(conn, "test@example.com")
    assert user is not None
    assert user["email"] == "test@example.com"


async def test_get_user_by_email_not_found(conn):
    user = await db.get_user_by_email(conn, "nobody@example.com")
    assert user is None


async def test_settings_crud(conn):
    await db.set_setting(conn, "test_key", "test_value")
    val = await db.get_setting(conn, "test_key")
    assert val == "test_value"

    await db.set_setting(conn, "test_key", "updated")
    val = await db.get_setting(conn, "test_key")
    assert val == "updated"


async def test_get_setting_not_found(conn):
    val = await db.get_setting(conn, "nonexistent")
    assert val is None
