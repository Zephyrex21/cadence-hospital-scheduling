"""Regression tests for the six high-severity bugs found in the audit."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import mongomock
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Acuity, AppointmentStatus, Role
from app.core.mongo import set_mongo_override
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.decision import SchedulingDecision
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment

T = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)


def make_doctor(db: Session, user_factory: Any, *, spec: str = "general", email: str = "doc@x.dev"):
    doctor = user_factory(Role.DOCTOR, email=email)
    db.add(DoctorProfile(user_id=doctor.id, specialty=spec))
    db.add(Shift(doctor_id=doctor.id, start_utc=T.replace(hour=8), end_utc=T.replace(hour=18)))
    db.commit()
    return doctor


def make_patient(db: Session, n: int, **extra: Any) -> Patient:
    patient = Patient(mrn=f"CAD-8{n:05d}", name=f"Pat {n}", date_of_birth=date(1990, 1, 1),
                      sex="other", **extra)
    db.add(patient)
    db.commit()
    return patient


def make_type(db: Session, name: str = "Consult", spec: str = "general", dur: int = 30):
    appt_type = AppointmentType(name=name, default_duration_min=dur, specialty=spec)
    db.add(appt_type)
    db.commit()
    return appt_type


def make_appt(db: Session, doctor: Any, patient: Patient, appt_type: Any, start: datetime,
              status: AppointmentStatus = AppointmentStatus.BOOKED) -> Appointment:
    appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, type_id=appt_type.id,
                       scheduled_start=start, scheduled_end=start + timedelta(minutes=30),
                       status=status, acuity=Acuity.A5)
    db.add(appt)
    db.commit()
    return appt


# --- 1. a profile edit must never erase existing patient data ---------------------------


def test_medical_only_edit_keeps_the_patients_existing_details(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    patient = make_patient(
        db_session, 1, contact="+91 98765 00000", city="Jaipur", blood_group="O+",
        emergency_contact="Ravi (husband) · +91 90000 12345", notes="Diabetic; on insulin.",
    )
    set_mongo_override(mongomock.MongoClient().high_fix)  # Mongo enabled AFTER the patient existed
    try:
        nurse = user_factory(Role.TRIAGE_NURSE)
        resp = client.put(f"/patients/{patient.id}/profile", headers=auth_headers(nurse),
                          json={"medical": {"blood_group": "O+", "conditions": ["Diabetes"]}})
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        row = db_session.get(Patient, patient.id)
        assert row is not None
        assert row.contact == "+91 98765 00000" and row.city == "Jaipur"
        assert row.emergency_contact == "Ravi (husband) · +91 90000 12345"
        assert row.notes == "Diabetic; on insulin."
        profile = resp.json()["profile"]  # …and the profile was seeded from them first
        assert profile["contact"]["phone"] == "+91 98765 00000"
        assert profile["address"]["city"] == "Jaipur"
        assert profile["medical"]["conditions"] == ["Diabetes"]
    finally:
        set_mongo_override(None)


def test_an_edit_only_mirrors_the_sections_it_changed(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    patient = make_patient(db_session, 2, contact="+91 90000 11111", city="Pune", blood_group="B+")
    set_mongo_override(mongomock.MongoClient().high_fix2)
    try:
        recep = user_factory(Role.RECEPTIONIST)
        resp = client.put(f"/patients/{patient.id}/profile", headers=auth_headers(recep),
                          json={"address": {"city": "Mumbai", "state": "Maharashtra"}})
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        row = db_session.get(Patient, patient.id)
        assert row is not None
        assert row.city == "Mumbai"                      # changed section is mirrored
        assert row.contact == "+91 90000 11111"          # untouched ones are left alone
        assert row.blood_group == "B+"
    finally:
        set_mongo_override(None)


# --- 2. emergency options expire; they can be re-planned --------------------------------


def _escalate_a1(client: TestClient, db: Session, user_factory: Any, auth_headers: Any):
    doctor = make_doctor(db, user_factory)
    appt_type = make_type(db)
    patient = make_patient(db, 3)
    db.add(TriageAssessment(patient_id=patient.id, nurse_id=doctor.id, acuity=Acuity.A1,
                            chief_complaint="chest pain"))
    db.commit()
    nurse = user_factory(Role.TRIAGE_NURSE)
    headers = auth_headers(nurse)
    body = {"patient_id": patient.id, "type_id": appt_type.id, "acuity": "a1", "now": T.isoformat()}
    plan = client.post("/emergencies/plan", headers=headers, json=body).json()
    committed = client.post("/emergencies/commit", headers=headers,
                            json={**body, "fingerprint": plan["fingerprint"]})
    assert committed.status_code == 200, committed.text
    record = db.scalar(select(SchedulingDecision))
    assert record is not None
    return record, headers


def test_stale_options_are_not_offered_and_replan_refreshes_them(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        record, _ = _escalate_a1(client, db_session, user_factory, auth_headers)
        decision_id = record.id
        fresh = client.get(f"/escalations/{decision_id}/options",
                           headers=auth_headers(user_factory(Role.ADMINISTRATOR, email="a@x.dev")))
        assert all(o["applicable"] and not o["expired"] for o in fresh.json()["options"])

    with time_machine.travel(T + timedelta(minutes=40), tick=False):
        admin = auth_headers(user_factory(Role.ADMINISTRATOR, email="b@x.dev"))
        stale = client.get(f"/escalations/{decision_id}/options", headers=admin).json()["options"]
        soonest = stale[0]
        assert soonest["expired"] is True and soonest["applicable"] is False

        replanned = client.post(f"/escalations/{decision_id}/replan", headers=admin)
        assert replanned.status_code == 200, replanned.text
        options = replanned.json()["options"]
        assert options and all(not o["expired"] for o in options)
        usable = next(o for o in options if o["applicable"])

        applied = client.post(f"/escalations/{decision_id}/apply", headers=admin,
                              json={"option_index": usable["index"], "note": "after re-plan"})
        assert applied.status_code == 200, applied.text


def test_replan_is_refused_for_a_resolved_escalation_and_for_doctors(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        record, nurse_headers = _escalate_a1(client, db_session, user_factory, auth_headers)
        doctor = user_factory(Role.DOCTOR, email="d2@x.dev")
        assert client.post(f"/escalations/{record.id}/replan",
                           headers=auth_headers(doctor)).status_code == 403
        done = client.post(f"/scheduling-decisions/{record.id}/resolve", headers=nurse_headers,
                           json={"note": "handled manually at the bedside"})
        assert done.status_code == 200, done.text
        assert client.post(f"/escalations/{record.id}/replan",
                           headers=nurse_headers).status_code == 409


# --- 3. a doctor sees one patient at a time ---------------------------------------------


def test_a_doctor_cannot_have_two_consultations_in_progress(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        other = make_doctor(db_session, user_factory, email="doc2@x.dev")
        appt_type = make_type(db_session)
        first = make_appt(db_session, doctor, make_patient(db_session, 4), appt_type, T)
        second = make_appt(db_session, doctor, make_patient(db_session, 5), appt_type,
                           T + timedelta(minutes=30))
        elsewhere = make_appt(db_session, other, make_patient(db_session, 6), appt_type, T)
        headers = auth_headers(doctor)

        assert client.post(f"/appointments/{first.id}/status", headers=headers,
                           json={"action": "start"}).status_code == 200
        blocked = client.post(f"/appointments/{second.id}/status", headers=headers,
                              json={"action": "start"})
        assert blocked.status_code == 409
        assert "in progress" in blocked.json()["error"]["message"]

        # a different doctor is unaffected, and finishing the first frees the next
        assert client.post(f"/appointments/{elsewhere.id}/status", headers=auth_headers(other),
                           json={"action": "start"}).status_code == 200
        assert client.post(f"/appointments/{first.id}/status", headers=headers,
                           json={"action": "complete"}).status_code == 200
        assert client.post(f"/appointments/{second.id}/status", headers=headers,
                           json={"action": "start"}).status_code == 200


# --- 4. booking respects specialty and active status ------------------------------------


def _book(
    client: TestClient, headers: dict[str, str], patient: Patient, doctor: Any, appt_type: Any
):
    return client.post("/appointments", headers=headers, json={
        "patient_id": patient.id, "doctor_id": doctor.id, "type_id": appt_type.id,
        "scheduled_start": T.replace(hour=11).isoformat()})


def test_booking_requires_a_matching_specialty(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T - timedelta(hours=1), tick=False):
        peds = make_doctor(db_session, user_factory, spec="pediatrics")
        cardiology = make_type(db_session, "Cardiology consultation", "cardiology")
        paediatric = make_type(db_session, "Child check-up", "pediatrics")
        patient = make_patient(db_session, 7)
        headers = auth_headers(user_factory(Role.RECEPTIONIST))

        bad = _book(client, headers, patient, peds, cardiology)
        assert bad.status_code == 422 and "cannot take" in bad.json()["error"]["message"]
        assert _book(client, headers, patient, peds, paediatric).status_code == 201

        # slots are never offered for a mismatched pair either
        slots = client.get("/slots", headers=headers, params={
            "doctor_id": peds.id, "type_id": cardiology.id, "day": T.isoformat()})
        assert slots.status_code == 200 and slots.json() == []


def test_a_deactivated_doctor_is_neither_listed_nor_bookable(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T - timedelta(hours=1), tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        patient = make_patient(db_session, 8)
        headers = auth_headers(user_factory(Role.RECEPTIONIST))
        assert doctor.id in [d["id"] for d in client.get("/doctors", headers=headers).json()]

        doctor.is_active = False
        db_session.commit()
        assert doctor.id not in [d["id"] for d in client.get("/doctors", headers=headers).json()]
        assert _book(client, headers, patient, doctor, appt_type).status_code == 422


# --- 5. the front desk can check patients in --------------------------------------------


def test_front_desk_can_check_in_and_mark_no_show_but_not_run_the_consultation(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        first = make_appt(db_session, doctor, make_patient(db_session, 9), appt_type, T)
        second = make_appt(db_session, doctor, make_patient(db_session, 10), appt_type,
                           T + timedelta(minutes=30))
        recep = auth_headers(user_factory(Role.RECEPTIONIST))
        nurse = auth_headers(user_factory(Role.TRIAGE_NURSE))

        assert client.post(f"/appointments/{first.id}/status", headers=recep,
                           json={"action": "check_in"}).status_code == 200
        assert client.post(f"/appointments/{second.id}/status", headers=nurse,
                           json={"action": "no_show"}).status_code == 200
        # starting / completing is clinical
        assert client.post(f"/appointments/{first.id}/status", headers=recep,
                           json={"action": "start"}).status_code == 403
        assert client.post(f"/appointments/{first.id}/status", headers=nurse,
                           json={"action": "complete"}).status_code == 403


def test_a_doctor_still_only_acts_on_their_own_patients(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        owner = make_doctor(db_session, user_factory)
        other = make_doctor(db_session, user_factory, email="doc3@x.dev")
        appt = make_appt(db_session, owner, make_patient(db_session, 11), make_type(db_session), T)
        assert client.post(f"/appointments/{appt.id}/status", headers=auth_headers(other),
                           json={"action": "check_in"}).status_code == 403


# --- 6. login does not care about the email's letter case -------------------------------


def test_login_ignores_email_case(client: TestClient, user_factory: Any) -> None:
    user_factory(Role.RECEPTIONIST, email="front@desk.dev")
    for typed in ("front@desk.dev", "Front@desk.dev", "FRONT@DESK.DEV"):
        resp = client.post("/auth/login", json={"email": typed, "password": "secret123"})
        assert resp.status_code == 200, f"{typed!r} -> {resp.status_code}"
    wrong = client.post("/auth/login", json={"email": "Front@desk.dev", "password": "nope"})
    assert wrong.status_code == 401
