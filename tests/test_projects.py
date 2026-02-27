import pytest

from inbox import db
from inbox.tools import projects, todos


async def test_create_project(conn):
    result = await projects.create_project(conn, "Work")
    assert result["project"]["name"] == "Work"


async def test_create_project_empty_name(conn):
    with pytest.raises(ValueError, match="name is required"):
        await projects.create_project(conn, "")


async def test_create_project_duplicate(conn):
    await projects.create_project(conn, "Work")
    with pytest.raises(ValueError, match="already exists"):
        await projects.create_project(conn, "Work")


async def test_create_project_duplicate_case_insensitive(conn):
    await projects.create_project(conn, "Work")
    with pytest.raises(ValueError, match="already exists"):
        await projects.create_project(conn, "work")


async def test_list_projects(conn):
    result = await projects.list_projects(conn)
    assert result["projects"] == []
    assert result["inbox_open"] == 0


async def test_list_projects_with_counts(conn):
    project = await db.create_project(conn, "Work")
    await todos.create_todo(conn, name="Open", project_id=project["id"])
    done = await todos.create_todo(conn, name="Done", project_id=project["id"])
    await todos.complete_todo(conn, done["todo"]["id"])
    await todos.create_todo(conn, name="Inbox todo")

    result = await projects.list_projects(conn)
    assert len(result["projects"]) == 1
    assert result["projects"][0]["open_count"] == 1
    assert result["projects"][0]["done_count"] == 1
    assert result["inbox_open"] == 1


async def test_update_project(conn):
    created = await projects.create_project(conn, "Old")
    result = await projects.update_project(conn, created["project"]["id"], "New")
    assert result["project"]["name"] == "New"


async def test_update_project_not_found(conn):
    with pytest.raises(ValueError, match="not found"):
        await projects.update_project(conn, 999, "New")


async def test_update_project_duplicate_name(conn):
    await projects.create_project(conn, "A")
    b = await projects.create_project(conn, "B")
    with pytest.raises(ValueError, match="already exists"):
        await projects.update_project(conn, b["project"]["id"], "A")


async def test_delete_project(conn):
    created = await projects.create_project(conn, "Work")
    pid = created["project"]["id"]
    await todos.create_todo(conn, name="Task", project_id=pid)

    result = await projects.delete_project(conn, pid)
    assert result["todos_moved_to_inbox"] == 1

    # Project should be gone from list
    listing = await projects.list_projects(conn)
    assert len(listing["projects"]) == 0

    # Todo should be in inbox
    search = await todos.search_todos(conn, project_id=0)
    assert search["count"] == 1
    assert search["todos"][0]["name"] == "Task"


async def test_delete_project_not_found(conn):
    with pytest.raises(ValueError, match="not found"):
        await projects.delete_project(conn, 999)
