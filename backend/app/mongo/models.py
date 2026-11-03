"""Pydantic models for the MongoDB profile documents.

These are the *write* contracts (validation happens here, before anything reaches
Mongo). A profile is a set of named sections; an update replaces only the sections it
carries. Everything is dumped with ``mode="json"`` so dates are BSON-safe ISO strings.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

SCHEMA_VERSION = 1


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _blank_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (None if isinstance(v, str) and not v.strip() else v) for k, v in data.items()
            }
        return data


Phone = Annotated[str, StringConstraints(max_length=30)]
Short = Annotated[str, StringConstraints(max_length=80)]
Line = Annotated[str, StringConstraints(max_length=120)]
BloodGroup = Annotated[str, StringConstraints(pattern=r"^(A|B|AB|O)[+-]$")]


# --- patient ------------------------------------------------------------------------


class Demographics(_Model):
    preferred_language: Annotated[str, StringConstraints(max_length=10)] | None = None
    occupation: Short | None = None


class PatientContact(_Model):
    phone: Phone | None = None
    alt_phone: Phone | None = None
    email: EmailStr | None = None


class Address(_Model):
    line1: Line | None = None
    line2: Line | None = None
    city: Short | None = None
    state: Short | None = None
    pin_code: Annotated[str, StringConstraints(pattern=r"^\d{6}$")] | None = None
    country: Short = "IN"


class EmergencyContact(_Model):
    name: Line
    relation: Annotated[str, StringConstraints(max_length=40)] | None = None
    phone: Phone | None = None
    is_primary: bool = False


class Allergy(_Model):
    substance: Short
    reaction: Line | None = None
    severity: Literal["mild", "moderate", "severe"] | None = None


class Medication(_Model):
    name: Short
    dose: Annotated[str, StringConstraints(max_length=40)] | None = None
    frequency: Annotated[str, StringConstraints(max_length=40)] | None = None


class Medical(_Model):
    """Reported by the patient / nurse for the front desk — not a clinical record."""

    blood_group: BloodGroup | None = None
    allergies: list[Allergy] = Field(default_factory=list, max_length=30)
    conditions: list[Annotated[str, StringConstraints(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=30
    )
    medications: list[Medication] = Field(default_factory=list, max_length=30)


class Insurance(_Model):
    scheme: Literal["none", "ayushman_bharat", "cghs", "esi", "private"] | None = None
    provider: Short | None = None
    policy_no: Annotated[str, StringConstraints(max_length=40)] | None = None


class Identifiers(_Model):
    # ABHA (Ayushman Bharat Health Account) — 14 digits, optionally dash-separated.
    # Aadhaar is deliberately NOT supported: storing it is legally restricted.
    abha_id: (
        Annotated[str, StringConstraints(pattern=r"^\d{2}-?\d{4}-?\d{4}-?\d{4}$")] | None
    ) = None


PATIENT_SECTIONS = (
    "demographics",
    "contact",
    "address",
    "emergency_contacts",
    "medical",
    "insurance",
    "identifiers",
    "notes",
)


class PatientProfileUpdate(_Model):
    """Any subset of sections; ``null`` clears a section."""

    demographics: Demographics | None = None
    contact: PatientContact | None = None
    address: Address | None = None
    emergency_contacts: list[EmergencyContact] | None = Field(default=None, max_length=10)
    medical: Medical | None = None
    insurance: Insurance | None = None
    identifiers: Identifiers | None = None
    notes: Annotated[str, StringConstraints(max_length=1000)] | None = None


# --- staff --------------------------------------------------------------------------


class StaffContact(_Model):
    phone: Phone | None = None
    alt_phone: Phone | None = None


class Employment(_Model):
    joined_on: date | None = None
    status: Literal["active", "on_leave", "inactive"] = "active"


class Registration(_Model):
    council: Line | None = None
    number: Annotated[str, StringConstraints(max_length=40)] | None = None


class Qualification(_Model):
    degree: Annotated[str, StringConstraints(max_length=60)]
    institution: Line | None = None
    year: Annotated[int, Field(ge=1950, le=2100)] | None = None


class Certification(_Model):
    name: Short
    expires_on: date | None = None


class DoctorDetails(_Model):
    registration: Registration | None = None
    qualifications: list[Qualification] = Field(default_factory=list, max_length=20)
    sub_specialties: list[Short] = Field(default_factory=list, max_length=20)
    experience_years: Annotated[int, Field(ge=0, le=70)] | None = None
    consultation_fee_inr: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    bio: Annotated[str, StringConstraints(max_length=600)] | None = None


ShiftPattern = Literal["day", "night", "rotating"]


class NurseDetails(_Model):
    registration: Registration | None = None
    qualifications: list[Qualification] = Field(default_factory=list, max_length=20)
    certifications: list[Certification] = Field(default_factory=list, max_length=30)
    ward: Short | None = None
    shift_pattern: ShiftPattern | None = None


class ReceptionDetails(_Model):
    counter: Short | None = None
    shift_pattern: ShiftPattern | None = None
    training: list[Short] = Field(default_factory=list, max_length=20)


STAFF_SECTIONS = (
    "employee_id",
    "department",
    "languages",
    "contact",
    "employment",
    "doctor",
    "nurse",
    "reception",
)


class StaffProfileUpdate(_Model):
    """Any subset of sections; ``null`` clears one. ``doctor`` / ``nurse`` / ``reception``
    must match the user's role (enforced by the service)."""

    employee_id: Annotated[str, StringConstraints(max_length=30)] | None = None
    department: Short | None = None
    languages: list[Annotated[str, StringConstraints(min_length=2, max_length=10)]] | None = Field(
        default=None, max_length=10
    )
    contact: StaffContact | None = None
    employment: Employment | None = None
    doctor: DoctorDetails | None = None
    nurse: NurseDetails | None = None
    reception: ReceptionDetails | None = None
