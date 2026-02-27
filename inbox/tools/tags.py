from inbox import db


async def list_tags(conn) -> dict:
    tags = await db.list_tags(conn)
    return {"tags": tags, "count": len(tags)}
