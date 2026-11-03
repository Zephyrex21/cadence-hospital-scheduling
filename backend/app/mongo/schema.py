"""Collection validators and indexes, applied idempotently at startup.

Pydantic validates everything the API writes; the ``$jsonSchema`` validators below are
the database-level safety net (wrong types / missing keys are refused even from a shell
or a future script). ``validationLevel=moderate`` keeps older documents readable.
"""

from __future__ import annotations

import logging
from typing import Any

PATIENTS = "patients"
STAFF = "staff_profiles"

_log = logging.getLogger("cadence.mongo")

_INT = ["int", "long"]

_PATIENT_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["patient_id", "mrn", "schema_version"],
        "properties": {
            "patient_id": {"bsonType": _INT},
            "mrn": {"bsonType": "string"},
            "schema_version": {"bsonType": _INT},
            "demographics": {"bsonType": "object"},
            "contact": {"bsonType": "object"},
            "address": {"bsonType": "object"},
            "emergency_contacts": {"bsonType": "array", "maxItems": 10},
            "medical": {"bsonType": "object"},
            "insurance": {"bsonType": "object"},
            "identifiers": {"bsonType": "object"},
            "notes": {"bsonType": "string", "maxLength": 1000},
        },
    }
}

_STAFF_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "role", "schema_version"],
        "properties": {
            "user_id": {"bsonType": _INT},
            "role": {"enum": ["receptionist", "triage_nurse", "doctor", "administrator"]},
            "schema_version": {"bsonType": _INT},
            "employee_id": {"bsonType": "string"},
            "department": {"bsonType": "string"},
            "languages": {"bsonType": "array"},
            "contact": {"bsonType": "object"},
            "employment": {"bsonType": "object"},
            "doctor": {"bsonType": "object"},
            "nurse": {"bsonType": "object"},
            "reception": {"bsonType": "object"},
        },
    }
}


def _apply_validator(mdb: Any, name: str, validator: dict[str, Any]) -> None:
    if name in mdb.list_collection_names():
        mdb.command("collMod", name, validator=validator, validationLevel="moderate")
    else:
        mdb.create_collection(name, validator=validator, validationLevel="moderate")


def apply_validators(mdb: Any) -> None:
    _apply_validator(mdb, PATIENTS, _PATIENT_VALIDATOR)
    _apply_validator(mdb, STAFF, _STAFF_VALIDATOR)


def ensure_indexes(mdb: Any) -> None:
    mdb[PATIENTS].create_index("patient_id", unique=True)
    mdb[PATIENTS].create_index("mrn", unique=True)
    mdb[STAFF].create_index("user_id", unique=True)
    mdb[STAFF].create_index("role")
    # Unique only when present, so many profiles may leave it unset.
    mdb[STAFF].create_index(
        "employee_id",
        unique=True,
        partialFilterExpression={"employee_id": {"$type": "string"}},
    )


def ensure_mongo_schema(mdb: Any) -> None:
    """Create collections, validators and indexes. Safe to run on every start."""
    apply_validators(mdb)
    ensure_indexes(mdb)
    _log.info("MongoDB schema ensured (%s, %s).", PATIENTS, STAFF)
