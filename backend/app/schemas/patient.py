"""Patient request/response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    sex: str = Field(min_length=1, max_length=16)
    contact: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    blood_group: str | None = Field(default=None, max_length=8)
    emergency_contact: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mrn: str
    name: str
    date_of_birth: date
    sex: str
    contact: str | None
    city: str | None = None
    blood_group: str | None = None
    emergency_contact: str | None = None
    notes: str | None = None
