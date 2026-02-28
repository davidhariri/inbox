from pydantic import BaseModel


class Todo(BaseModel):
    id: int
    name: str
    link: str | None = None
    due_date: str | None = None
    priority: str | None = None
    project_id: int | None = None
    tags: list[str] = []
    created_at: str
    updated_at: str
    completed_at: str | None = None


class Project(BaseModel):
    id: int
    name: str
    created_at: str
    updated_at: str
    open_count: int = 0
    done_count: int = 0


class TagCount(BaseModel):
    tag: str
    count: int


# --- REST API request models ---


class CreateTodoInput(BaseModel):
    name: str
    link: str | None = None
    due_date: str | None = None
    priority: str | None = None
    project_id: int | None = None
    tags: list[str] | None = None


class UpdateTodoRequest(BaseModel):
    name: str | None = None
    link: str | None = None
    due_date: str | None = None
    priority: str | None = None
    project_id: int | None = None
    tags: list[str] | None = None


class IdsRequest(BaseModel):
    ids: list[int]


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
