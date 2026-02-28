"""REST API tests for project endpoints."""


async def test_create_project(api_client):
    resp = await api_client.post(
        "/api/projects", json={"name": "Work", "description": "Work stuff"}
    )
    assert resp.status_code == 200
    assert resp.json()["project"]["name"] == "Work"


async def test_list_projects(api_client):
    await api_client.post("/api/projects", json={"name": "Alpha"})
    await api_client.post("/api/projects", json={"name": "Beta"})

    resp = await api_client.get("/api/projects")
    assert resp.status_code == 200
    assert len(resp.json()["projects"]) == 2


async def test_update_project(api_client):
    resp = await api_client.post("/api/projects", json={"name": "Old"})
    project_id = resp.json()["project"]["id"]

    resp = await api_client.patch(f"/api/projects/{project_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["project"]["name"] == "New"


async def test_delete_project(api_client):
    resp = await api_client.post("/api/projects", json={"name": "Doomed"})
    project_id = resp.json()["project"]["id"]

    resp = await api_client.delete(f"/api/projects/{project_id}")
    assert resp.status_code == 200

    resp = await api_client.get("/api/projects")
    assert len(resp.json()["projects"]) == 0


async def test_create_duplicate_project(api_client):
    await api_client.post("/api/projects", json={"name": "Unique"})
    resp = await api_client.post("/api/projects", json={"name": "Unique"})
    assert resp.status_code == 422


async def test_delete_project_not_found(api_client):
    resp = await api_client.delete("/api/projects/9999")
    assert resp.status_code == 404
