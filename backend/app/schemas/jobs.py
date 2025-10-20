from datetime import datetime

from pydantic import BaseModel


class Job(BaseModel):
    id: str
    status: str
    submitted_at: datetime
    workspace_id: str
