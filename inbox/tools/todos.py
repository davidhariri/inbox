import re
from datetime import UTC, datetime

from inbox import db

VALID_PRIORITIES = ("high", "medium", "low")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_TAG_LENGTH = 50


def _validate_priority(priority: str | None) -> None:
    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValueError(
            f"priority must be one of: {', '.join(VALID_PRIORITIES)} — got '{priority}'"
        )


def _validate_due_date(due_date: str | None) -> None:
    if due_date is not None:
        if not DATE_RE.match(due_date):
            raise ValueError(f"due_date must be YYYY-MM-DD format — got '{due_date}'")
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"due_date is not a valid date — got '{due_date}'")


def _validate_tags(tags: list[str] | None) -> None:
    if tags is None:
        return
    for tag in tags:
        if not tag or not tag.strip():
            raise ValueError("tags must not be empty strings")
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(
                f"each tag must be {MAX_TAG_LENGTH} characters or fewer "
                f"— '{tag[:20]}...' is {len(tag)}"
            )


async def _project_name(conn, project_id: int | None) -> str:
    if project_id is None:
        return "Inbox"
    project = await db.get_project(conn, project_id)
    return project["name"] if project else "Unknown"


async def _context(conn, todo: dict) -> dict:
    """Build rich context to return alongside a todo."""
    project_name = await _project_name(conn, todo["project_id"])
    open_count = await db.count_open_todos(
        conn, project_id=todo["project_id"] if todo["project_id"] else 0
    )
    overdue_count = await db.count_overdue_todos(conn)

    ctx = {"project": project_name, "open_in_project": open_count}
    if overdue_count > 0:
        ctx["overdue_total"] = overdue_count
    return ctx


async def create_todo(
    conn,
    name: str,
    link: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    project_id: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    if not name or not name.strip():
        raise ValueError("name is required and must not be empty")
    _validate_priority(priority)
    _validate_due_date(due_date)
    _validate_tags(tags)

    if project_id is not None:
        project = await db.get_project(conn, project_id)
        if not project:
            raise ValueError(f"project_id {project_id} does not exist")

    todo = await db.create_todo(
        conn,
        name=name.strip(),
        link=link,
        due_date=due_date,
        priority=priority,
        project_id=project_id,
        tags=tags,
    )
    context = await _context(conn, todo)
    return {"todo": todo, **context}


async def bulk_create_todos(
    conn,
    names: list[str],
    project_id: int | None = None,
) -> dict:
    if not names:
        raise ValueError("names must not be empty")

    if project_id is not None:
        project = await db.get_project(conn, project_id)
        if not project:
            raise ValueError(f"project_id {project_id} does not exist")

    created = []
    for name in names:
        if not name or not name.strip():
            raise ValueError("each name must be non-empty")
        todo = await db.create_todo(conn, name=name.strip(), project_id=project_id)
        created.append(todo)

    project_name = await _project_name(conn, project_id)
    open_count = await db.count_open_todos(conn, project_id=project_id if project_id else 0)

    return {
        "todos": created,
        "count": len(created),
        "project": project_name,
        "open_in_project": open_count,
    }


async def bulk_complete_todos(conn, ids: list[int]) -> dict:
    if not ids:
        raise ValueError("ids must not be empty")

    completed = []
    skipped = []
    for id in ids:
        todo = await db.get_todo(conn, id)
        if not todo:
            raise ValueError(f"todo {id} not found")
        if todo["completed_at"]:
            skipped.append({"id": id, "name": todo["name"], "reason": "already completed"})
            continue
        todo = await db.complete_todo(conn, id)
        completed.append(todo)

    result = {"completed": completed, "count": len(completed)}
    if skipped:
        result["skipped"] = skipped
    return result


async def bulk_delete_todos(conn, ids: list[int]) -> dict:
    if not ids:
        raise ValueError("ids must not be empty")

    deleted = []
    for id in ids:
        todo = await db.get_todo(conn, id)
        if not todo:
            raise ValueError(f"todo {id} not found")
        await db.delete_todo(conn, id)
        deleted.append({"id": id, "name": todo["name"]})

    return {"deleted": deleted, "count": len(deleted)}


async def get_todo(conn, id: int) -> dict:
    todo = await db.get_todo(conn, id)
    if not todo:
        raise ValueError(f"todo {id} not found")
    context = await _context(conn, todo)
    return {"todo": todo, **context}


async def update_todo(
    conn,
    id: int,
    name: str | None = None,
    link: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    project_id: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    existing = await db.get_todo(conn, id)
    if not existing:
        raise ValueError(f"todo {id} not found")

    fields = {}
    if name is not None:
        if not name.strip():
            raise ValueError("name must not be empty")
        fields["name"] = name.strip()
    if link is not None:
        fields["link"] = link
    if due_date is not None:
        _validate_due_date(due_date)
        fields["due_date"] = due_date
    if priority is not None:
        _validate_priority(priority)
        fields["priority"] = priority
    if project_id is not None:
        project = await db.get_project(conn, project_id)
        if not project:
            raise ValueError(f"project_id {project_id} does not exist")
        fields["project_id"] = project_id
    if tags is not None:
        _validate_tags(tags)
        fields["tags"] = tags

    if not fields:
        raise ValueError("no fields to update — provide at least one field to change")

    todo = await db.update_todo(conn, id, **fields)
    context = await _context(conn, todo)
    return {"todo": todo, **context}


async def complete_todo(conn, id: int) -> dict:
    existing = await db.get_todo(conn, id)
    if not existing:
        raise ValueError(f"todo {id} not found")
    if existing["completed_at"]:
        raise ValueError(f"todo {id} is already completed")

    todo = await db.complete_todo(conn, id)
    context = await _context(conn, todo)

    remaining = context["open_in_project"]
    if remaining == 0:
        context["message"] = f"All todos in {context['project']} are done!"

    return {"todo": todo, **context}


async def reopen_todo(conn, id: int) -> dict:
    existing = await db.get_todo(conn, id)
    if not existing:
        raise ValueError(f"todo {id} not found")
    if not existing["completed_at"]:
        raise ValueError(f"todo {id} is not completed")

    todo = await db.reopen_todo(conn, id)
    context = await _context(conn, todo)
    return {"todo": todo, **context}


async def delete_todo(conn, id: int) -> dict:
    existing = await db.get_todo(conn, id)
    if not existing:
        raise ValueError(f"todo {id} not found")

    await db.delete_todo(conn, id)
    return {"deleted": True, "id": id, "name": existing["name"]}


async def search_todos(
    conn,
    query: str | None = None,
    tags: list[str] | None = None,
    project_id: int | None = None,
    due_before: str | None = None,
    priority: str | None = None,
    status: str = "open",
) -> dict:
    if status not in ("open", "done", "all"):
        raise ValueError(f"status must be one of: open, done, all — got '{status}'")
    if priority is not None:
        _validate_priority(priority)
    if due_before is not None:
        _validate_due_date(due_before)

    todos = await db.search_todos(
        conn,
        query=query,
        tags=tags,
        project_id=project_id,
        due_before=due_before,
        priority=priority,
        status=status,
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    overdue = [
        t for t in todos if t["due_date"] and t["due_date"] < today and not t["completed_at"]
    ]

    result = {"todos": todos, "count": len(todos)}
    if overdue:
        result["overdue_count"] = len(overdue)
    return result
