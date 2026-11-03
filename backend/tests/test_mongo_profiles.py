"""MongoDB profile store: patient + staff profiles layered on the Postgres records.

Mongo is exercised with ``mongomock`` (a PyMongo-compatible in-memory fake), injected
through the same seam the app uses (``set_mongo_override``).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import MagicMock

import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.mongo import set_mongo_override
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.user import User

Headers = Callable[[User], dict[str, str]]
Users = Callable[..., User]

_PATIENT = {"name": "Jane Doe", "date_of_birth": "1990-06-15", "sex": "female"}


@pytest.fixture()
def mdb() -> Iterator[Any]:
    database = mongomock.MongoClient().cadence_test
    set_mongo_override(database)
    try:
        yield database
    finally:
        set_mongo_override(None)


def _register(client: TestClient, headers: dict[str, str], **extra: Any) -> dict[str, Any]:
    resp = client.post("/patients", json={**_PATIENT, **extra}, headers=headers)
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


# --- feature flag -------------------------------------------------------------------


def test_profile_store_is_optional(
    client: TestClient, user_factory: Users, auth_headers: Headers
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    patient = _register(client, recep)

    read = client.get(f"/patients/{patient['id']}/profile", headers=recep)
    assert read.status_code == 200
    body = read.json()
    assert body["enabled"] is False and body["profile"] is None
    assert body["patient"]["mrn"] == patient["mrn"]

    write = client.put(
        f"/patients/{patient['id']}/profile",
        json={"contact": {"phone": "+91 90000 11111"}},
        headers=recep,
    )
    assert write.status_code == 501
    assert write.json()["error"]["code"] == "profile_store_disabled"


def test_mongo_health_reports_state(client: TestClient, mdb: Any) -> None:
    assert client.get("/health/mongo").json() == {"enabled": True, "ok": True}


def test_mongo_health_when_disabled(client: TestClient) -> None:
    assert client.get("/health/mongo").json() == {"enabled": False, "ok": False}


# --- patient profile ----------------------------------------------------------------


def test_registering_a_patient_creates_a_base_profile(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    patient = _register(
        client,
        recep,
        contact="+91 90000 12345",
        city="Pune",
        blood_group="O+",
        emergency_contact="Asha Rao (mother) · +91 90000 54321",
    )
    doc = mdb["patients"].find_one({"patient_id": patient["id"]})
    assert doc is not None
    assert doc["mrn"] == patient["mrn"]
    assert doc["contact"]["phone"] == "+91 90000 12345"
    assert doc["address"]["city"] == "Pune"
    assert doc["medical"]["blood_group"] == "O+"
    assert doc["emergency_contacts"] == [
        {"name": "Asha Rao", "relation": "mother", "phone": "+91 90000 54321", "is_primary": True}
    ]
    assert doc["schema_version"] == 1


def test_receptionist_updates_profile_and_legacy_columns_follow(
    client: TestClient,
    mdb: Any,
    db_session: Session,
    user_factory: Users,
    auth_headers: Headers,
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    patient = _register(client, recep)

    resp = client.put(
        f"/patients/{patient['id']}/profile",
        json={
            "contact": {"phone": "+91 98765 43210", "email": "jane@example.com"},
            "address": {"line1": "12 MG Road", "city": "Bengaluru", "state": "Karnataka",
                        "pin_code": "560001"},
            "emergency_contacts": [
                {"name": "John Doe", "relation": "husband", "phone": "+91 90000 00001",
                 "is_primary": True}
            ],
            "demographics": {"preferred_language": "kn"},
            "insurance": {"scheme": "ayushman_bharat", "policy_no": "PMJAY-1"},
        },
        headers=recep,
    )
    assert resp.status_code == 200, resp.text
    profile = resp.json()["profile"]
    assert profile["address"]["city"] == "Bengaluru"
    assert profile["address"]["country"] == "IN"
    assert profile["contact"]["email"] == "jane@example.com"

    db_session.expire_all()
    row = db_session.get(Patient, patient["id"])
    assert row is not None
    # The list / search page reads these legacy columns; they mirror the profile.
    assert row.contact == "+91 98765 43210"
    assert row.city == "Bengaluru"
    assert row.emergency_contact == "John Doe (husband) · +91 90000 00001"


def test_sections_are_replaced_not_merged_and_others_untouched(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    patient = _register(client, recep)
    url = f"/patients/{patient['id']}/profile"
    client.put(url, json={"contact": {"phone": "1", "alt_phone": "2"},
                          "address": {"city": "Pune"}}, headers=recep)
    client.put(url, json={"contact": {"phone": "3"}}, headers=recep)

    profile = client.get(url, headers=recep).json()["profile"]
    assert profile["contact"] == {"phone": "3"}  # alt_phone gone: section replaced
    assert profile["address"]["city"] == "Pune"  # untouched section kept


def test_receptionist_cannot_edit_medical_but_nurse_can(
    client: TestClient,
    mdb: Any,
    db_session: Session,
    user_factory: Users,
    auth_headers: Headers,
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    nurse = auth_headers(user_factory(Role.TRIAGE_NURSE))
    patient = _register(client, recep)
    url = f"/patients/{patient['id']}/profile"
    medical = {"medical": {"blood_group": "AB-", "allergies": [
        {"substance": "Penicillin", "reaction": "rash", "severity": "moderate"}],
        "conditions": ["Asthma"]}}

    denied = client.put(url, json=medical, headers=recep)
    assert denied.status_code == 403
    assert "medical" in denied.json()["error"]["message"]

    ok = client.put(url, json=medical, headers=nurse)
    assert ok.status_code == 200
    assert ok.json()["profile"]["medical"]["allergies"][0]["substance"] == "Penicillin"
    db_session.expire_all()
    row = db_session.get(Patient, patient["id"])
    assert row is not None and row.blood_group == "AB-"


def test_doctor_is_read_only_on_patient_profiles(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    doctor = auth_headers(user_factory(Role.DOCTOR))
    patient = _register(client, recep)
    url = f"/patients/{patient['id']}/profile"

    assert client.get(url, headers=doctor).status_code == 200
    assert client.put(url, json={"notes": "x"}, headers=doctor).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"address": {"pin_code": "12"}},
        {"medical": {"allergies": [{"substance": "Dust", "severity": "catastrophic"}]}},
        {"medical": {"blood_group": "Z+"}},
        {"contact": {"email": "not-an-email"}},
        {"insurance": {"scheme": "free-money"}},
    ],
)
def test_invalid_profile_data_is_rejected(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers,
    payload: dict[str, Any],
) -> None:
    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    patient = _register(client, admin)
    resp = client.put(f"/patients/{patient['id']}/profile", json=payload, headers=admin)
    assert resp.status_code == 422


def test_unknown_patient_is_404(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    assert client.get("/patients/999/profile", headers=admin).status_code == 404


def test_profile_updates_are_audited(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    from app.models.audit import AuditLog

    admin_user = user_factory(Role.ADMINISTRATOR)
    admin = auth_headers(admin_user)
    patient = _register(client, admin)
    client.put(f"/patients/{patient['id']}/profile", json={"notes": "hello"}, headers=admin)

    from sqlalchemy import select

    from app.core.db import get_db
    from app.main import app

    session = next(app.dependency_overrides[get_db]())
    entry = session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "patient_profile")
    ).one()
    assert entry.entity_id == str(patient["id"])
    assert entry.actor_id == admin_user.id
    assert entry.after == {"sections": ["notes"]}


# --- outages ------------------------------------------------------------------------


def _broken_database() -> MagicMock:
    broken = MagicMock()
    broken.__getitem__.side_effect = ServerSelectionTimeoutError("atlas unreachable")
    broken.command.side_effect = ServerSelectionTimeoutError("atlas unreachable")
    return broken


def test_reads_degrade_gracefully_when_mongo_is_down(
    client: TestClient, user_factory: Users, auth_headers: Headers
) -> None:
    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    patient = _register(client, admin)  # registration must also survive the outage
    set_mongo_override(_broken_database())
    try:
        resp = client.get(f"/patients/{patient['id']}/profile", headers=admin)
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True and body["available"] is False
        assert body["profile"] is None and body["patient"]["mrn"] == patient["mrn"]

        write = client.put(
            f"/patients/{patient['id']}/profile", json={"notes": "x"}, headers=admin
        )
        assert write.status_code == 424
        assert write.json()["error"]["code"] == "profile_store_error"
        assert client.get("/health/mongo").json() == {"enabled": True, "ok": False}
    finally:
        set_mongo_override(None)


def test_registration_still_works_when_mongo_is_down(
    client: TestClient, user_factory: Users, auth_headers: Headers
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    set_mongo_override(_broken_database())
    try:
        patient = _register(client, recep)
    finally:
        set_mongo_override(None)
    assert patient["mrn"].startswith("CAD-")


# --- indexes / validators -----------------------------------------------------------


def test_indexes_are_idempotent_and_enforce_uniqueness(mdb: Any) -> None:
    from app.mongo.schema import ensure_indexes

    ensure_indexes(mdb)
    ensure_indexes(mdb)  # safe to run on every start

    mdb["patients"].insert_one({"patient_id": 1, "mrn": "CAD-1", "schema_version": 1})
    with pytest.raises(DuplicateKeyError):
        mdb["patients"].insert_one({"patient_id": 1, "mrn": "CAD-2", "schema_version": 1})
    with pytest.raises(DuplicateKeyError):
        mdb["patients"].insert_one({"patient_id": 2, "mrn": "CAD-1", "schema_version": 1})

    mdb["staff_profiles"].insert_one({"user_id": 1, "role": "doctor", "schema_version": 1})
    with pytest.raises(DuplicateKeyError):
        mdb["staff_profiles"].insert_one({"user_id": 1, "role": "doctor", "schema_version": 1})
    # employee_id is unique only when present: many profiles may leave it unset
    mdb["staff_profiles"].insert_one({"user_id": 2, "role": "doctor", "schema_version": 1})
    mdb["staff_profiles"].insert_one({"user_id": 3, "role": "doctor", "schema_version": 1})


# --- staff profiles -----------------------------------------------------------------


def test_admin_lists_staff_with_and_without_profiles(
    client: TestClient, mdb: Any, db_session: Session, user_factory: Users,
    auth_headers: Headers,
) -> None:
    admin_user = user_factory(Role.ADMINISTRATOR)
    doctor = user_factory(Role.DOCTOR)
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="cardiology"))
    db_session.commit()
    db_session.expire_all()  # the shared test session cached doctor_profile=None
    user_factory(Role.TRIAGE_NURSE)

    resp = client.put(
        f"/staff/{doctor.id}/profile",
        json={"employee_id": "DOC-1", "department": "Cardiology", "languages": ["en", "hi"],
              "doctor": {"registration": {"council": "Delhi Medical Council", "number": "DMC-1"},
                         "qualifications": [{"degree": "MD", "institution": "AIIMS", "year": 2010}],
                         "experience_years": 12, "consultation_fee_inr": 800}},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200, resp.text

    rows = client.get("/staff", headers=auth_headers(admin_user)).json()
    by_role = {r["user"]["role"]: r for r in rows}
    assert by_role["doctor"]["user"]["specialty"] == "cardiology"
    assert by_role["doctor"]["profile"]["doctor"]["experience_years"] == 12
    assert by_role["triage_nurse"]["profile"] is None
    assert "password_hash" not in str(rows)


def test_role_specific_details_must_match_the_users_role(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    nurse = user_factory(Role.TRIAGE_NURSE)
    resp = client.put(
        f"/staff/{nurse.id}/profile",
        json={"doctor": {"experience_years": 3}},
        headers=admin,
    )
    assert resp.status_code == 422
    ok = client.put(
        f"/staff/{nurse.id}/profile",
        json={"nurse": {"ward": "Emergency", "shift_pattern": "rotating",
                        "certifications": [{"name": "BLS", "expires_on": "2027-01-31"}]}},
        headers=admin,
    )
    assert ok.status_code == 200
    assert ok.json()["profile"]["nurse"]["certifications"][0]["name"] == "BLS"


def test_staff_can_edit_only_their_own_contact_details(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    doctor = user_factory(Role.DOCTOR)
    other = user_factory(Role.TRIAGE_NURSE)
    headers = auth_headers(doctor)

    own = client.put(f"/staff/{doctor.id}/profile",
                     json={"contact": {"phone": "+91 90000 99999"}, "languages": ["en"]},
                     headers=headers)
    assert own.status_code == 200

    assert client.put(f"/staff/{doctor.id}/profile", json={"employee_id": "X"},
                      headers=headers).status_code == 403  # admin-only field
    assert client.put(f"/staff/{other.id}/profile", json={"contact": {"phone": "1"}},
                      headers=headers).status_code == 403  # someone else's profile


def test_clearing_a_scalar_field_removes_it(
    client: TestClient, mdb: Any, user_factory: Users, auth_headers: Headers
) -> None:
    admin_user = user_factory(Role.ADMINISTRATOR)
    admin = auth_headers(admin_user)
    nurse = user_factory(Role.TRIAGE_NURSE)
    client.put(f"/staff/{nurse.id}/profile", json={"employee_id": "NUR-1"}, headers=admin)
    client.put(f"/staff/{nurse.id}/profile", json={"employee_id": None}, headers=admin)
    doc = mdb["staff_profiles"].find_one({"user_id": nurse.id})
    assert doc is not None and "employee_id" not in doc


# --- backfill -----------------------------------------------------------------------


def test_backfill_builds_profiles_from_postgres_and_is_idempotent(
    client: TestClient, db_session: Session, user_factory: Users, auth_headers: Headers
) -> None:
    from app.services.profiles import backfill_profiles

    recep = user_factory(Role.RECEPTIONIST)
    user_factory(Role.DOCTOR)
    patient = _register(client, auth_headers(recep), city="Delhi",
                        emergency_contact="Raj (brother) · +91 90000 77777")

    database = mongomock.MongoClient().backfill_test
    first = backfill_profiles(db_session, database)
    second = backfill_profiles(db_session, database)

    assert first == {"patients": 1, "staff": 2}
    assert second == {"patients": 0, "staff": 0}  # nothing left to create
    doc = database["patients"].find_one({"patient_id": patient["id"]})
    assert doc is not None and doc["emergency_contacts"][0]["relation"] == "brother"
    assert database["staff_profiles"].count_documents({}) == 2


# --- real MongoDB (optional) ----------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("CADENCE_TEST_MONGODB_URI"),
    reason="set CADENCE_TEST_MONGODB_URI to run against a real MongoDB",
)
def test_validators_are_enforced_by_a_real_mongodb() -> None:
    from pymongo import MongoClient
    from pymongo.errors import WriteError

    from app.mongo.schema import ensure_mongo_schema

    client: MongoClient[dict[str, Any]] = MongoClient(os.environ["CADENCE_TEST_MONGODB_URI"])
    client.drop_database("cadence_validator_test")
    database = client["cadence_validator_test"]
    try:
        ensure_mongo_schema(database)
        ensure_mongo_schema(database)  # idempotent (collMod path)
        database["patients"].insert_one({"patient_id": 1, "mrn": "CAD-1", "schema_version": 1})
        with pytest.raises(WriteError):  # missing required keys
            database["patients"].insert_one({"mrn": "CAD-2"})
        with pytest.raises(WriteError):  # wrong type
            database["patients"].insert_one(
                {"patient_id": "two", "mrn": "CAD-3", "schema_version": 1}
            )
        with pytest.raises(WriteError):  # role outside the enum
            database["staff_profiles"].insert_one(
                {"user_id": 1, "role": "wizard", "schema_version": 1}
            )
    finally:
        client.drop_database("cadence_validator_test")


# --- demo seeding -------------------------------------------------------------------


def test_demo_profiles_seed_rich_data_without_overwriting_edits(db_session: Session) -> None:
    from sqlalchemy import select

    from app.seed import _ensure_patients, _ensure_staff
    from app.seed_profiles import seed_profiles
    from app.services.profiles import backfill_profiles

    _ensure_staff(db_session, "pw-for-tests")
    _ensure_patients(db_session)
    db_session.commit()

    database = mongomock.MongoClient().seed_test
    seed_profiles(db_session, database)
    irfan = db_session.scalars(select(Patient).where(Patient.mrn == "CAD-100003")).one()
    doc = database["patients"].find_one({"patient_id": irfan.id})
    assert doc is not None
    assert doc["medical"]["allergies"][0]["substance"] == "Penicillin"
    assert doc["medical"]["blood_group"] == "A+"  # legacy value merged with the new detail
    assert doc["address"]["pin_code"] == "500034"

    # An edit made in the app survives the next restart's seeding.
    database["patients"].update_one({"patient_id": irfan.id}, {"$set": {"notes": "edited"}})
    seed_profiles(db_session, database)
    again = database["patients"].find_one({"patient_id": irfan.id})
    assert again is not None and again["notes"] == "edited"

    staff = database["staff_profiles"].count_documents({"doctor": {"$exists": True}})
    assert staff == 3
    assert backfill_profiles(db_session, database) == {"patients": 0, "staff": 0}
