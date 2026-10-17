"""User response schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.enums import Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role
    is_active: bool
