"""REST API tests for todo endpoints."""


async def test_create_single_todo(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "Buy milk"}])
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["todos"][0]["name"] == "Buy milk"


async def test_create_multiple_todos(api_client):
    resp = await api_client.post(
        "/api/todos",
        json=[{"name": "Task 1"}, {"name": "Task 2", "priority": "high"}],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2


async def test_create_todo_validation_error(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": ""}])
    assert resp.status_code == 422


async def test_search_todos(api_client):
    await api_client.post("/api/todos", json=[{"name": "Alpha"}, {"name": "Beta"}])
    resp = await api_client.get("/api/todos")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2


async def test_search_todos_by_priority(api_client):
    await api_client.post(
        "/api/todos",
        json=[{"name": "Urgent", "priority": "high"}, {"name": "Later", "priority": "low"}],
    )
    resp = await api_client.get("/api/todos", params={"priority": "high"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["todos"][0]["name"] == "Urgent"


async def test_get_todo(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "Find me"}])
    todo_id = resp.json()["todos"][0]["id"]

    resp = await api_client.get(f"/api/todos/{todo_id}")
    assert resp.status_code == 200
    assert resp.json()["todo"]["name"] == "Find me"


async def test_get_todo_not_found(api_client):
    resp = await api_client.get("/api/todos/9999")
    assert resp.status_code == 404


async def test_update_todo(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "Old name"}])
    todo_id = resp.json()["todos"][0]["id"]

    resp = await api_client.patch(f"/api/todos/{todo_id}", json={"name": "New name"})
    assert resp.status_code == 200
    assert resp.json()["todo"]["name"] == "New name"


async def test_delete_todo(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "Delete me"}])
    todo_id = resp.json()["todos"][0]["id"]

    resp = await api_client.delete(f"/api/todos/{todo_id}")
    assert resp.status_code == 200

    resp = await api_client.get(f"/api/todos/{todo_id}")
    assert resp.status_code == 404


async def test_complete_todos(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "A"}, {"name": "B"}])
    ids = [t["id"] for t in resp.json()["todos"]]

    resp = await api_client.post("/api/todos/complete", json={"ids": ids})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


async def test_reopen_todos(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "Reopen me"}])
    todo_id = resp.json()["todos"][0]["id"]

    await api_client.post("/api/todos/complete", json={"ids": [todo_id]})

    resp = await api_client.post("/api/todos/reopen", json={"ids": [todo_id]})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


async def test_bulk_delete_todos(api_client):
    resp = await api_client.post("/api/todos", json=[{"name": "X"}, {"name": "Y"}])
    ids = [t["id"] for t in resp.json()["todos"]]

    resp = await api_client.post("/api/todos/delete", json={"ids": ids})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


async def test_search_by_tags(api_client):
    await api_client.post(
        "/api/todos",
        json=[
            {"name": "Tagged", "tags": ["work", "urgent"]},
            {"name": "Untagged"},
        ],
    )
    resp = await api_client.get("/api/todos", params={"tags": "work"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
