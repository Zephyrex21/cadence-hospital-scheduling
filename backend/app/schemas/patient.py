"""Patient request/response schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Sex = Literal["male", "female", "other"]
BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
_OLDEST_BIRTH_YEAR = 1900


class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    date_of_birth: date
    sex: Sex
    contact: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    blood_group: BloodGroup | None = None
    emergency_contact: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def _tidy_name(cls, value: Any) -> Any:
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator(
        "contact", "city", "blood_group", "emergency_contact", "notes", mode="before"
    )
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("date_of_birth")
    @classmethod
    def _plausible_birth_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        if value.year < _OLDEST_BIRTH_YEAR:
            raise ValueError(f"Date of birth cannot be before {_OLDEST_BIRTH_YEAR}")
        return value


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
