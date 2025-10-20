from pydantic import BaseModel


class Workspace(BaseModel):
    id: str
    name: str
    description: str | None = None
