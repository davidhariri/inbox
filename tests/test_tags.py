from inbox.tools import tags, todos


async def test_list_tags_empty(conn):
    result = await tags.list_tags(conn)
    assert result["tags"] == []
    assert result["count"] == 0


async def test_list_tags(conn):
    await todos.create_todo(conn, name="A", tags=["bug", "urgent"])
    await todos.create_todo(conn, name="B", tags=["bug"])
    await todos.create_todo(conn, name="C", tags=["feature"])

    result = await tags.list_tags(conn)
    assert result["count"] == 3

    tag_map = {t["tag"]: t["count"] for t in result["tags"]}
    assert tag_map["bug"] == 2
    assert tag_map["urgent"] == 1
    assert tag_map["feature"] == 1


async def test_list_tags_excludes_deleted(conn):
    created = await todos.create_todo(conn, name="A", tags=["bug"])
    await todos.delete_todo(conn, created["todo"]["id"])

    result = await tags.list_tags(conn)
    assert result["count"] == 0
