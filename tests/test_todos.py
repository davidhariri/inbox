import pytest

from inbox import db
from inbox.tools import todos


async def test_create_todo(conn):
    result = await todos.create_todo(conn, name="Buy milk")
    assert result["todo"]["name"] == "Buy milk"
    assert result["todo"]["project_id"] is None
    assert result["project"] == "Inbox"
    assert result["open_in_project"] == 1


async def test_create_todo_with_all_fields(conn):
    project = await db.create_project(conn, "Shopping")
    result = await todos.create_todo(
        conn,
        name="Buy eggs",
        link="https://example.com",
        due_date="2026-03-15",
        priority="high",
        project_id=project["id"],
        tags=["groceries", "urgent"],
    )
    todo = result["todo"]
    assert todo["link"] == "https://example.com"
    assert todo["due_date"] == "2026-03-15"
    assert todo["priority"] == "high"
    assert todo["project_id"] == project["id"]
    assert todo["tags"] == ["groceries", "urgent"]
    assert result["project"] == "Shopping"


async def test_create_todo_empty_name(conn):
    with pytest.raises(ValueError, match="name is required"):
        await todos.create_todo(conn, name="")


async def test_create_todo_invalid_priority(conn):
    with pytest.raises(ValueError, match="priority must be one of"):
        await todos.create_todo(conn, name="Test", priority="urgent")


async def test_create_todo_invalid_date(conn):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        await todos.create_todo(conn, name="Test", due_date="March 15")


async def test_create_todo_invalid_date_value(conn):
    with pytest.raises(ValueError, match="not a valid date"):
        await todos.create_todo(conn, name="Test", due_date="2026-02-30")


async def test_create_todo_tag_too_long(conn):
    with pytest.raises(ValueError, match="50 characters"):
        await todos.create_todo(conn, name="Test", tags=["x" * 51])


async def test_create_todo_empty_tag(conn):
    with pytest.raises(ValueError, match="must not be empty"):
        await todos.create_todo(conn, name="Test", tags=[""])


async def test_create_todo_invalid_project(conn):
    with pytest.raises(ValueError, match="does not exist"):
        await todos.create_todo(conn, name="Test", project_id=999)


async def test_bulk_create_todos_inbox(conn):
    result = await todos.bulk_create_todos(conn, names=["Buy milk", "Buy eggs", "Buy bread"])
    assert result["count"] == 3
    assert result["project"] == "Inbox"
    assert result["open_in_project"] == 3
    assert [t["name"] for t in result["todos"]] == ["Buy milk", "Buy eggs", "Buy bread"]


async def test_bulk_create_todos_with_project(conn):
    project = await db.create_project(conn, "Groceries")
    result = await todos.bulk_create_todos(
        conn, names=["Apples", "Bananas"], project_id=project["id"]
    )
    assert result["count"] == 2
    assert result["project"] == "Groceries"
    assert all(t["project_id"] == project["id"] for t in result["todos"])


async def test_bulk_create_todos_empty_list(conn):
    with pytest.raises(ValueError, match="must not be empty"):
        await todos.bulk_create_todos(conn, names=[])


async def test_bulk_create_todos_empty_name(conn):
    with pytest.raises(ValueError, match="non-empty"):
        await todos.bulk_create_todos(conn, names=["Valid", ""])


async def test_bulk_create_todos_invalid_project(conn):
    with pytest.raises(ValueError, match="does not exist"):
        await todos.bulk_create_todos(conn, names=["Test"], project_id=999)


async def test_get_todo(conn):
    created = await todos.create_todo(conn, name="Test")
    result = await todos.get_todo(conn, created["todo"]["id"])
    assert result["todo"]["name"] == "Test"


async def test_get_todo_not_found(conn):
    with pytest.raises(ValueError, match="not found"):
        await todos.get_todo(conn, 999)


async def test_update_todo(conn):
    created = await todos.create_todo(conn, name="Old name")
    result = await todos.update_todo(conn, created["todo"]["id"], name="New name")
    assert result["todo"]["name"] == "New name"


async def test_update_todo_tags(conn):
    created = await todos.create_todo(conn, name="Test", tags=["a"])
    result = await todos.update_todo(conn, created["todo"]["id"], tags=["a", "b"])
    assert result["todo"]["tags"] == ["a", "b"]


async def test_update_todo_not_found(conn):
    with pytest.raises(ValueError, match="not found"):
        await todos.update_todo(conn, 999, name="New")


async def test_update_todo_no_fields(conn):
    created = await todos.create_todo(conn, name="Test")
    with pytest.raises(ValueError, match="no fields"):
        await todos.update_todo(conn, created["todo"]["id"])


async def test_complete_todo(conn):
    created = await todos.create_todo(conn, name="Test")
    result = await todos.complete_todo(conn, created["todo"]["id"])
    assert result["todo"]["completed_at"] is not None


async def test_complete_todo_already_done(conn):
    created = await todos.create_todo(conn, name="Test")
    await todos.complete_todo(conn, created["todo"]["id"])
    with pytest.raises(ValueError, match="already completed"):
        await todos.complete_todo(conn, created["todo"]["id"])


async def test_complete_last_todo_in_project(conn):
    project = await db.create_project(conn, "Test Project")
    created = await todos.create_todo(conn, name="Only todo", project_id=project["id"])
    result = await todos.complete_todo(conn, created["todo"]["id"])
    assert result.get("message") == "All todos in Test Project are done!"


async def test_reopen_todo(conn):
    created = await todos.create_todo(conn, name="Test")
    await todos.complete_todo(conn, created["todo"]["id"])
    result = await todos.reopen_todo(conn, created["todo"]["id"])
    assert result["todo"]["completed_at"] is None


async def test_reopen_todo_not_completed(conn):
    created = await todos.create_todo(conn, name="Test")
    with pytest.raises(ValueError, match="not completed"):
        await todos.reopen_todo(conn, created["todo"]["id"])


async def test_delete_todo(conn):
    created = await todos.create_todo(conn, name="Test")
    result = await todos.delete_todo(conn, created["todo"]["id"])
    assert result["deleted"] is True

    # Should not be findable after deletion
    with pytest.raises(ValueError, match="not found"):
        await todos.get_todo(conn, created["todo"]["id"])


async def test_delete_todo_not_found(conn):
    with pytest.raises(ValueError, match="not found"):
        await todos.delete_todo(conn, 999)


async def test_search_todos_default(conn):
    await todos.create_todo(conn, name="First")
    await todos.create_todo(conn, name="Second")
    result = await todos.search_todos(conn)
    assert result["count"] == 2


async def test_search_todos_by_status(conn):
    await todos.create_todo(conn, name="Open one")
    done = await todos.create_todo(conn, name="Done one")
    await todos.complete_todo(conn, done["todo"]["id"])

    open_result = await todos.search_todos(conn, status="open")
    assert open_result["count"] == 1
    assert open_result["todos"][0]["name"] == "Open one"

    done_result = await todos.search_todos(conn, status="done")
    assert done_result["count"] == 1
    assert done_result["todos"][0]["name"] == "Done one"

    all_result = await todos.search_todos(conn, status="all")
    assert all_result["count"] == 2


async def test_search_todos_by_project(conn):
    project = await db.create_project(conn, "Work")
    await todos.create_todo(conn, name="Inbox todo")
    await todos.create_todo(conn, name="Work todo", project_id=project["id"])

    inbox_result = await todos.search_todos(conn, project_id=0)
    assert inbox_result["count"] == 1
    assert inbox_result["todos"][0]["name"] == "Inbox todo"

    project_result = await todos.search_todos(conn, project_id=project["id"])
    assert project_result["count"] == 1
    assert project_result["todos"][0]["name"] == "Work todo"


async def test_search_todos_by_priority(conn):
    await todos.create_todo(conn, name="Urgent", priority="high")
    await todos.create_todo(conn, name="Chill", priority="low")

    result = await todos.search_todos(conn, priority="high")
    assert result["count"] == 1
    assert result["todos"][0]["name"] == "Urgent"


async def test_search_todos_by_tags(conn):
    await todos.create_todo(conn, name="Bug fix", tags=["bug", "urgent"])
    await todos.create_todo(conn, name="Feature", tags=["feature"])

    result = await todos.search_todos(conn, tags=["bug"])
    assert result["count"] == 1
    assert result["todos"][0]["name"] == "Bug fix"

    # AND semantics
    result = await todos.search_todos(conn, tags=["bug", "urgent"])
    assert result["count"] == 1

    result = await todos.search_todos(conn, tags=["bug", "feature"])
    assert result["count"] == 0


async def test_search_todos_by_due_before(conn):
    await todos.create_todo(conn, name="Soon", due_date="2026-03-01")
    await todos.create_todo(conn, name="Later", due_date="2026-12-31")
    await todos.create_todo(conn, name="No date")

    result = await todos.search_todos(conn, due_before="2026-06-01")
    assert result["count"] == 1
    assert result["todos"][0]["name"] == "Soon"


async def test_search_todos_fts(conn):
    await todos.create_todo(conn, name="Buy groceries")
    await todos.create_todo(conn, name="Fix the car")

    result = await todos.search_todos(conn, query="groceries")
    assert result["count"] == 1
    assert result["todos"][0]["name"] == "Buy groceries"


async def test_search_todos_invalid_status(conn):
    with pytest.raises(ValueError, match="status must be"):
        await todos.search_todos(conn, status="invalid")


async def test_search_todos_excludes_deleted(conn):
    created = await todos.create_todo(conn, name="Will be deleted")
    await todos.delete_todo(conn, created["todo"]["id"])
    result = await todos.search_todos(conn, status="all")
    assert result["count"] == 0


async def test_search_todos_order(conn):
    """Due date ascending (nulls last), then created_at descending."""
    await todos.create_todo(conn, name="No date")
    await todos.create_todo(conn, name="Later", due_date="2026-12-31")
    await todos.create_todo(conn, name="Sooner", due_date="2026-03-01")

    result = await todos.search_todos(conn)
    names = [t["name"] for t in result["todos"]]
    assert names == ["Sooner", "Later", "No date"]
