"""Patient request/response schemas."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Sex = Literal["male", "female", "other"]
BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
_OLDEST_BIRTH_YEAR = 1900
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_CHARS = re.compile(r"^[0-9+\-().,/\s]+$")


def check_contact(value: str) -> str:
    """A contact is a phone number (7-15 digits, usual separators allowed) or an e-mail."""
    text = value.strip()
    if "@" in text:
        if not _EMAIL.match(text):
            raise ValueError("Enter a valid e-mail address or phone number")
        return text
    digits = sum(ch.isdigit() for ch in text)
    if not _PHONE_CHARS.match(text) or not 7 <= digits <= 15:
        raise ValueError("Enter a valid phone number (7-15 digits) or e-mail address")
    return text


class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    date_of_birth: date
    sex: Sex
    contact: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    blood_group: BloodGroup | None = None
    emergency_contact: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)
    # Registering someone who matches an existing name + date of birth is refused (it is
    # usually a double entry) unless the clerk explicitly confirms.
    allow_duplicate: bool = False

    @field_validator("contact")
    @classmethod
    def _valid_contact(cls, value: str | None) -> str | None:
        return None if value is None else check_contact(value)

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
