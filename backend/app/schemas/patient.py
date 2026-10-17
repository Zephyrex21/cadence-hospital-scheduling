"""Patient request/response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    sex: str = Field(min_length=1, max_length=16)
    contact: str | None = Field(default=None, max_length=120)


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mrn: str
    name: str
    date_of_birth: date
    sex: str
    contact: str | None
