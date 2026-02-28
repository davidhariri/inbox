"""REST API tests for tag endpoints."""


async def test_list_tags_empty(api_client):
    resp = await api_client.get("/api/tags")
    assert resp.status_code == 200
    assert resp.json()["tags"] == []


async def test_list_tags_with_data(api_client):
    await api_client.post(
        "/api/todos",
        json=[
            {"name": "A", "tags": ["work"]},
            {"name": "B", "tags": ["work", "urgent"]},
        ],
    )

    resp = await api_client.get("/api/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    tag_names = [t["tag"] for t in data["tags"]]
    assert "work" in tag_names
    assert "urgent" in tag_names
