from pydantic import BaseModel, EmailStr


class User(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None = None
