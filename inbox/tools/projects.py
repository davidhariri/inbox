from inbox import db


async def create_project(conn, name: str, description: str | None = None) -> dict:
    if not name or not name.strip():
        raise ValueError("name is required and must not be empty")

    existing = await db.list_projects(conn)
    for p in existing:
        if p["name"].lower() == name.strip().lower():
            raise ValueError(f"a project named '{p['name']}' already exists")

    project = await db.create_project(conn, name.strip(), description=description)
    return {"project": project}


async def list_projects(conn) -> dict:
    projects = await db.list_projects(conn)
    inbox_count = await db.count_open_todos(conn, project_id=0)
    return {"inbox_open": inbox_count, "projects": projects}


async def update_project(
    conn, id: int, name: str | None = None, description: str | None = None
) -> dict:
    existing = await db.get_project(conn, id)
    if not existing:
        raise ValueError(f"project {id} not found")

    fields = {}
    if name is not None:
        if not name.strip():
            raise ValueError("name must not be empty")
        all_projects = await db.list_projects(conn)
        for p in all_projects:
            if p["name"].lower() == name.strip().lower() and p["id"] != id:
                raise ValueError(f"a project named '{p['name']}' already exists")
        fields["name"] = name.strip()
    if description is not None:
        fields["description"] = description

    if not fields:
        return {"project": existing}

    project = await db.update_project(conn, id, **fields)
    return {"project": project}


async def delete_project(conn, id: int) -> dict:
    existing = await db.get_project(conn, id)
    if not existing:
        raise ValueError(f"project {id} not found")

    result = await db.delete_project(conn, id)
    return result
