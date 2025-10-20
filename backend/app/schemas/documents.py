from datetime import datetime

from pydantic import BaseModel


class Document(BaseModel):
    id: str
    name: str
    created_at: datetime
    workspace_id: str
