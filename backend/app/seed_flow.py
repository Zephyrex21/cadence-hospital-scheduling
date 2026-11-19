"""Realistic clinic activity for the demo: busy doctors, a week of history, emergencies, messages.

``seed.py`` writes a few *scripted* scenarios (a live consultation, an escalation, one displaced
patient). This module fills the clinic around them so every screen looks like a working
hospital rather than a sparse demo:

* ``ensure_clinic_flow``     - dense, varied schedules for every doctor, 3 days back to 6 ahead;
* ``advance_demo_clock``     - brings untouched demo appointments in line with the current time;
* ``ensure_history``         - a week of past emergencies (some displacing a patient) and
                               resolved escalations, each with triage, decision and audit trail;
* ``ensure_notifications``   - a message record for every displaced patient.

Everything is deterministic and idempotent: running it again adds nothing that exists already.
Real users' work is never touched (only appointments still at ``version == 1`` are advanced).
"""

from __future__ import annotations

import hashlib
import logging
import random
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    Acuity,
    AppointmentOrigin,
    AppointmentStatus,
    AuditAction,
)
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.audit import AuditLog
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.triage import TriageAssessment
from app.models.user import User
from app.scheduling.availability import Interval, reserved_blocks
from app.services.notifications import extract_phone, moved_message

log = logging.getLogger("cadence.seed")

DAYS_BACK = 6
PUSH = timedelta(minutes=15)  # how far a displaced patient is pushed back in the history
DAYS_AHEAD = 6
GAP = timedelta(minutes=15)  # minimum breathing room between two appointments

# Fraction of each session that gets booked: busiest today and in the recent past, thinning out
# for dates further ahead (people book a few days out, not a month).
_FILL = {-6: 0.74, -5: 0.78, -4: 0.80, -3: 0.82, -2: 0.85, -1: 0.86, 0: 0.80,
         1: 0.66, 2: 0.56, 3: 0.46, 4: 0.40, 5: 0.34, 6: 0.30}

_ACUITY_MIX = [(Acuity.A5, 42), (Acuity.A4, 33), (Acuity.A3, 17), (Acuity.A2, 8)]

_ACTIVE = (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS)


def _weighted(rng: random.Random, pairs: Sequence[tuple[Any, int]]) -> Any:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


def _local(value: datetime) -> date:
    return value.astimezone(settings.clinic_tz).date()


def _at(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, tzinfo=settings.clinic_tz).astimezone(UTC)


# --------------------------------------------------------------------------------------------
# Dense, realistic schedules
# --------------------------------------------------------------------------------------------


def _type_mix(
    specialty: str, types: dict[str, AppointmentType]
) -> list[tuple[AppointmentType, int]]:
    from app import seed as S

    main = types[S._SPECIALTY_TYPE[specialty]]
    follow = types["Follow-up visit"]
    if specialty == "general":
        return [(main, 52), (follow, 30), (types["Extended consultation"], 18)]
    return [(main, 68), (follow, 32)]


def _eligible(specialty: str, age: int, sex: str) -> bool:
    if specialty == "pediatrics":
        return age < 16
    if specialty == "gynaecology":
        return sex == "female" and 16 <= age <= 62
    return age >= 14


def _template(
    rng: random.Random, start: datetime, end: datetime, mix: list[tuple[AppointmentType, int]],
    fill: float,
) -> list[tuple[datetime, AppointmentType]]:
    """A session's appointments, decided purely from the RNG (never from the database), so the
    same day always produces the same plan however many times the seed runs."""
    items: list[tuple[datetime, AppointmentType]] = []
    cursor = start + timedelta(minutes=rng.choice([0, 0, 15]))
    while True:
        appt_type = _weighted(rng, mix)
        length = timedelta(minutes=appt_type.default_duration_min)
        if cursor + length > end:
            break
        if rng.random() > fill:  # an open slot (a cancellation, or simply not booked)
            cursor += timedelta(minutes=15 * rng.choice([1, 2, 2, 3]))
            continue
        items.append((cursor, appt_type))
        cursor += length + timedelta(minutes=15 * _weighted(rng, [(1, 78), (2, 14), (3, 8)]))
    return items


def lateness(email: str, day: date) -> timedelta:
    """How far behind schedule a doctor is running on a given day (0 for roughly half of them).

    Real clinics run late: consultations overrun, so the next patients are already waiting.
    Deterministic per doctor and day, so it is stable across seeds."""
    rng = random.Random(f"late:{email}:{day}")
    if rng.random() >= 0.5:
        return timedelta(0)
    return timedelta(minutes=rng.choice([10, 15, 20, 25, 30]))


def _arrived(rng: random.Random, start: datetime, doctor_now: datetime) -> bool:
    """Patients turn up early: most are in the waiting room an hour ahead, many two hours."""
    lead = start - doctor_now
    if lead <= timedelta(minutes=60):
        return rng.random() < 0.90
    if lead <= timedelta(minutes=120):
        return rng.random() < 0.55
    return lead <= timedelta(minutes=180) and rng.random() < 0.15


def _status_for(
    rng: random.Random, start: datetime, end: datetime, now: datetime,
    late: timedelta = timedelta(0),
) -> AppointmentStatus:
    doctor_now = now - late  # where this doctor actually is in the day
    if end <= doctor_now:
        roll = rng.random()
        if roll < 0.06:
            return AppointmentStatus.NO_SHOW
        return AppointmentStatus.CANCELLED if roll < 0.10 else AppointmentStatus.COMPLETED
    if start <= doctor_now < end:
        return AppointmentStatus.IN_PROGRESS
    if _arrived(rng, start, doctor_now):
        return AppointmentStatus.CHECKED_IN
    if start > now and rng.random() < 0.05:
        return AppointmentStatus.CANCELLED
    return AppointmentStatus.BOOKED


def ensure_clinic_flow(db: Session, now: datetime) -> int:
    """Fill every doctor's days around what already exists. Returns appointments added."""
    from app import seed as S

    doctors = {
        u.email: u for u in db.scalars(select(User).where(User.email.in_(list(S._DOCTORS))))
    }
    types = {t.name: t for t in db.scalars(select(AppointmentType))}
    patients = list(db.scalars(
        select(Patient).where(Patient.mrn.in_([row[0] for row in S._PATIENTS])).order_by(Patient.id)
    ))
    receptionists = list(db.scalars(
        select(User).where(User.email.like("receptionist%@cadence.dev")).order_by(User.id)
    ))
    if not doctors or not patients or not receptionists:
        return 0

    today = _local(now)
    first, last = today - timedelta(days=DAYS_BACK), today + timedelta(days=DAYS_AHEAD + 1)
    window_lo, window_hi = _at(first, time(0, 0)), _at(last, time(0, 0))
    existing = list(db.execute(
        select(Appointment.doctor_id, Appointment.patient_id, Appointment.scheduled_start,
               Appointment.scheduled_end, Appointment.status)
        .where(Appointment.scheduled_start >= window_lo, Appointment.scheduled_start < window_hi)
    ))
    busy: dict[int, list[tuple[datetime, datetime]]] = {}
    starts: dict[int, set[datetime]] = {}
    used_patients: dict[date, set[int]] = {}
    for doctor_id, patient_id, s, e, _status in existing:
        s = s.replace(tzinfo=UTC) if s.tzinfo is None else s
        e = e.replace(tzinfo=UTC) if e.tzinfo is None else e
        starts.setdefault(doctor_id, set()).add(s)
        # Cancelled slots keep counting as taken: planning must look the same on every run, or
        # each re-seed would quietly fill the gaps that cancellations left behind.
        busy.setdefault(doctor_id, []).append((s, e))
        used_patients.setdefault(_local(s), set()).add(patient_id)

    roster = [(p.id, 2026 - p.date_of_birth.year, p.sex.value if hasattr(p.sex, "value") else p.sex)
              for p in patients]
    added = 0
    for offset in range(-DAYS_BACK, DAYS_AHEAD + 1):
        day = today + timedelta(days=offset)
        shuffled = list(roster)
        random.Random(f"pool:{day}").shuffle(shuffled)
        used = used_patients.setdefault(day, set())
        fill = _FILL[offset] * (0.55 if day.weekday() == 6 else 1.0)  # quieter Sundays
        sessions = [Interval(_at(day, a), _at(day, b)) for a, b in S._SESSIONS]
        held = reserved_blocks(
            sessions, settings.emergency_reserve_blocks, settings.emergency_reserve_min
        )
        for email, specialty in S._DOCTORS.items():
            doctor = doctors.get(email)
            if doctor is None:
                continue
            mix = _type_mix(specialty, types)
            taken = busy.setdefault(doctor.id, [])
            seen_starts = starts.setdefault(doctor.id, set())
            new: list[Appointment] = []
            for session_index, session in enumerate(sessions):
                # One independent random stream per session (the plan) and per appointment (its
                # status and acuity): what an earlier run accepted can never shift a later plan.
                plan_rng = random.Random(f"flow:{email}:{day}:{session_index}")
                for start, appt_type in _template(
                    plan_rng, session.start, session.end, mix, fill
                ):
                    end = start + timedelta(minutes=appt_type.default_duration_min)
                    if start in seen_starts:
                        continue  # planned (and inserted) by an earlier run
                    if any(start - GAP < e and s < end + GAP for s, e in taken):
                        continue  # would crowd something that is already booked
                    if any(h.start < end and start < h.end for h in held):
                        continue  # kept free for emergencies
                    patient_id = next(
                        (pid for pid, age, sex in shuffled
                         if pid not in used and _eligible(specialty, age, sex)), None)
                    if patient_id is None:
                        continue
                    used.add(patient_id)
                    taken.append((start, end))
                    item_rng = random.Random(f"item:{email}:{start.isoformat()}")
                    status = _status_for(
                        item_rng, start, end, now,
                        lateness(email, day) if offset == 0 else timedelta(0),
                    )
                    acuity = (
                        Acuity.A5 if appt_type.name == "Follow-up visit"
                        else _weighted(item_rng, _ACUITY_MIX)
                    )
                    new.append(Appointment(
                        patient_id=patient_id, doctor_id=doctor.id, type_id=appt_type.id,
                        scheduled_start=start, scheduled_end=end, status=status,
                        origin=AppointmentOrigin.BOOKED, acuity=acuity, version=1,
                    ))
            if new:
                added += _insert(db, new, receptionists, doctor, now)
    return added


def _insert(
    db: Session, appts: list[Appointment], receptionists: list[User], doctor: User,
    now: datetime,
) -> int:
    try:
        with db.begin_nested():
            db.add_all(appts)
            db.flush()
        saved = appts
    except IntegrityError:  # a clash with something real: place what fits, one by one
        saved = []
        for appt in appts:
            try:
                with db.begin_nested():
                    db.add(Appointment(
                        patient_id=appt.patient_id, doctor_id=appt.doctor_id,
                        type_id=appt.type_id, scheduled_start=appt.scheduled_start,
                        scheduled_end=appt.scheduled_end, status=appt.status,
                        origin=appt.origin, acuity=appt.acuity, version=1,
                    ))
                    db.flush()
                saved.append(appt)
            except IntegrityError:
                continue
    for appt in saved:
        booked_by = receptionists[appt.id % len(receptionists)]
        lead = random.Random(f"booked:{appt.doctor_id}:{appt.scheduled_start.isoformat()}")
        booked_at = min(appt.scheduled_start, now) - timedelta(
            days=lead.randint(1, 5), hours=lead.randint(0, 6))
        db.add(AuditLog(
            entity_type="appointment", entity_id=str(appt.id), action=AuditAction.CREATE.value,
            actor_id=booked_by.id, before=None,
            after={"patient_id": appt.patient_id, "doctor_id": appt.doctor_id,
                   "status": "booked", "scheduled_start": appt.scheduled_start.isoformat()},
            reason="Demo seed: appointment booked", created_at=booked_at,
        ))
        if appt.status != AppointmentStatus.BOOKED:
            actor = doctor if appt.status in (
                AppointmentStatus.IN_PROGRESS, AppointmentStatus.COMPLETED) else booked_by
            when = (appt.scheduled_end if appt.status in (
                AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW)
                else min(appt.scheduled_start, now))
            db.add(AuditLog(
                entity_type="appointment", entity_id=str(appt.id),
                action=AuditAction.UPDATE.value, actor_id=actor.id,
                before={"status": "booked"}, after={"status": appt.status.value},
                reason=f"Demo seed: marked {appt.status.value.replace('_', ' ')}",
                created_at=when,
            ))
    return len(saved)


# --------------------------------------------------------------------------------------------
# Keep the demo in step with the clock
# --------------------------------------------------------------------------------------------


def advance_demo_clock(db: Session, now: datetime) -> None:
    """Appointments nobody has touched follow the clock: finished ones complete, the one in the
    room is "in progress", and people due soon have arrived. Anything a real user has acted on
    (version > 1) is left exactly as they left it."""
    from app import seed as S

    mrns = [row[0] for row in S._PATIENTS]
    ids = list(db.scalars(select(Patient.id).where(Patient.mrn.in_(mrns))))
    if not ids:
        return
    horizon_lo, horizon_hi = now - timedelta(days=2), now + timedelta(hours=1)
    rows = list(db.scalars(
        select(Appointment).where(
            Appointment.patient_id.in_(ids), Appointment.version == 1,
            Appointment.origin == AppointmentOrigin.BOOKED,
            Appointment.status.in_(_ACTIVE),
            Appointment.scheduled_start >= horizon_lo, Appointment.scheduled_start < horizon_hi,
        ).order_by(Appointment.scheduled_start)
    ))
    in_room = {
        a.doctor_id for a in db.scalars(select(Appointment).where(
            Appointment.status == AppointmentStatus.IN_PROGRESS))
    }
    email_of = {u.id: u.email for u in db.scalars(select(User).where(User.id.in_(
        {a.doctor_id for a in rows}) if rows else User.id == -1))}
    today = _local(now)
    for appt in rows:
        start, end = _utc(appt.scheduled_start), _utc(appt.scheduled_end)
        day = _local(start)
        late = lateness(email_of.get(appt.doctor_id, ""), day) if day == today else timedelta(0)
        doctor_now = now - late
        if end <= doctor_now - timedelta(minutes=5):
            appt.status = (AppointmentStatus.NO_SHOW
                           if appt.status == AppointmentStatus.BOOKED and appt.id % 13 == 0
                           else AppointmentStatus.COMPLETED)
            if appt.status == AppointmentStatus.COMPLETED:
                in_room.discard(appt.doctor_id)
        elif start <= doctor_now < end and appt.doctor_id not in in_room:
            appt.status = AppointmentStatus.IN_PROGRESS
            in_room.add(appt.doctor_id)
        elif (appt.status == AppointmentStatus.BOOKED and start > doctor_now
              and start - doctor_now <= timedelta(minutes=90) and appt.id % 5 != 0):
            appt.status = AppointmentStatus.CHECKED_IN


# --------------------------------------------------------------------------------------------
# A week of history: emergencies, displacements, resolved escalations
# --------------------------------------------------------------------------------------------

# (complaint, acuity, vitals)
_EMERGENCIES: list[tuple[str, Acuity, dict[str, Any]]] = [
    ("Chest pain radiating to left arm, 40 minutes", Acuity.A2,
     {"blood_pressure": "148/94", "heart_rate_bpm": 104, "temperature_c": 36.9,
      "oxygen_saturation_pct": 96}),
    ("Acute breathlessness with wheeze, not settling with inhaler", Acuity.A2,
     {"blood_pressure": "132/84", "heart_rate_bpm": 118, "temperature_c": 37.2,
      "oxygen_saturation_pct": 91}),
    ("Sudden severe headache with vomiting", Acuity.A2,
     {"blood_pressure": "168/102", "heart_rate_bpm": 92, "temperature_c": 36.8,
      "oxygen_saturation_pct": 98}),
    ("High fever with rigors for three days", Acuity.A2,
     {"blood_pressure": "102/66", "heart_rate_bpm": 114, "temperature_c": 39.6,
      "oxygen_saturation_pct": 97}),
    ("Fall on stairs; wrist swollen and deformed", Acuity.A3,
     {"blood_pressure": "126/80", "heart_rate_bpm": 88, "temperature_c": 36.8,
      "oxygen_saturation_pct": 99}),
    ("Persistent vomiting and abdominal pain, two days", Acuity.A3,
     {"blood_pressure": "110/70", "heart_rate_bpm": 100, "temperature_c": 37.8,
      "oxygen_saturation_pct": 98}),
    ("Palpitations since morning, settled while waiting", Acuity.A3,
     {"blood_pressure": "134/86", "heart_rate_bpm": 112, "temperature_c": 36.7,
      "oxygen_saturation_pct": 98}),
    ("Hives and lip swelling after starting an antibiotic", Acuity.A3,
     {"blood_pressure": "122/78", "heart_rate_bpm": 96, "temperature_c": 36.9,
      "oxygen_saturation_pct": 97}),
    ("Deep forearm laceration, bleeding controlled", Acuity.A3,
     {"blood_pressure": "130/82", "heart_rate_bpm": 90, "temperature_c": 36.7,
      "oxygen_saturation_pct": 99}),
    ("Child with fever 39.2 °C and ear pain, drinking poorly", Acuity.A3,
     {"heart_rate_bpm": 130, "temperature_c": 39.2, "oxygen_saturation_pct": 98}),
]

_RESOLUTIONS = [
    "Directed to the cardiology bay; ECG and troponin sent, admitted under observation.",
    "Patient transferred to the emergency ward; family informed by the nurse in charge.",
    "Seen immediately by the duty physician; routine bookings eased back by the front desk.",
    "Escalated to the on-call consultant, who took the patient in the resuscitation room.",
]


def _key(day: date, n: int) -> str:
    return f"cadence-demo-hist-{day.isoformat()}-{n}"


def ensure_history(db: Session, now: datetime) -> int:
    """Past emergencies (some displacing a patient) and resolved escalations."""
    from app import seed as S

    nurses = list(db.scalars(select(User).where(User.email.like("nurse%@cadence.dev"))
                             .order_by(User.id)))
    admin = db.scalar(select(User).where(User.email == "admin@cadence.dev"))
    if not nurses or admin is None:
        return 0
    doctors = list(db.scalars(select(User).where(User.email.in_(list(S._DOCTORS)))))
    doctors.sort(key=lambda u: list(S._DOCTORS).index(u.email))
    types = {t.name: t for t in db.scalars(select(AppointmentType))}
    patients = {p.id: p for p in db.scalars(select(Patient).where(
        Patient.mrn.in_([row[0] for row in S._PATIENTS])))}
    today = _local(now)
    made = 0
    for back in range(1, 7):
        day = today - timedelta(days=back)
        have = set(db.scalars(select(SchedulingDecision.idempotency_key).where(
            SchedulingDecision.idempotency_key.like(f"cadence-demo-hist-{day.isoformat()}-%"))))
        rng = random.Random(f"hist:{day}")
        count = rng.choice([2, 3, 3, 4])
        for n in range(count):
            if _key(day, n) in have:
                continue
            made += _one_emergency(db, rng, day, n, nurses, doctors, types, patients, now,
                                   displace=(n % 3 == 1))
        if back in (2, 5) and _key(day, 9) not in have:
            made += _one_escalation(db, rng, day, nurses, admin, patients, doctors, now)
    return made


def _active_for(db: Session, doctor_id: int, day: date) -> list[Appointment]:
    return list(db.scalars(select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status != AppointmentStatus.CANCELLED,
        Appointment.scheduled_start >= _at(day, time(0, 0)),
        Appointment.scheduled_start < _at(day + timedelta(days=1), time(0, 0)),
    ).order_by(Appointment.scheduled_start)))


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _one_emergency(
    db: Session, rng: random.Random, day: date, n: int, nurses: list[User],
    doctors: list[User], types: dict[str, AppointmentType], patients: dict[int, Patient],
    now: datetime, *, displace: bool,
) -> int:
    doctor = doctors[(day.toordinal() + n * 3) % len(doctors)]
    appts = _active_for(db, doctor.id, day)
    busy_patients = set(db.scalars(select(Appointment.patient_id).where(
        Appointment.scheduled_start >= _at(day, time(0, 0)),
        Appointment.scheduled_start < _at(day + timedelta(days=1), time(0, 0)))))
    candidates = [p for pid, p in patients.items() if pid not in busy_patients]
    if not candidates:
        return 0
    patient = candidates[rng.randrange(len(candidates))]
    complaint, acuity, vitals = _EMERGENCIES[rng.randrange(len(_EMERGENCIES))]

    moved: Appointment | None = None
    slot_start = slot_end = None
    if displace:
        eligible = [
            appt for appt, nxt in zip(appts, appts[1:], strict=False)
            if appt.status == AppointmentStatus.COMPLETED and appt.version == 1
            and _utc(appt.scheduled_start).astimezone(settings.clinic_tz).hour >= 10
            and _utc(nxt.scheduled_start) - _utc(appt.scheduled_end) >= PUSH
        ]
        if eligible:
            moved = eligible[rng.randrange(min(len(eligible), 12))]
            slot_start = _utc(moved.scheduled_start)
            slot_end = slot_start + PUSH  # a quick emergency review in the patient's slot
    if slot_start is None:  # a free 30-minute hole instead
        for before, after in zip(appts, appts[1:], strict=False):
            hole_start = _utc(before.scheduled_end) + timedelta(minutes=5)
            if (_utc(after.scheduled_start) - hole_start >= timedelta(minutes=40)
                    and hole_start.astimezone(settings.clinic_tz).hour >= 10):
                slot_start, slot_end = hole_start, hole_start + timedelta(minutes=30)
                break
    if slot_start is None or slot_end is None:
        return 0

    appt_type = types["Follow-up visit"] if (slot_end - slot_start) <= timedelta(minutes=15) \
        else types["General OPD consultation"]
    nurse = nurses[(day.toordinal() + n) % len(nurses)]
    key = _key(day, n)
    created = slot_start - timedelta(minutes=rng.randint(18, 40))
    try:
        with db.begin_nested():
            if moved is not None:
                moved.scheduled_start = _utc(moved.scheduled_start) + PUSH
                moved.scheduled_end = _utc(moved.scheduled_end) + PUSH
                moved.displacement_count += 1
                moved.version += 1
                db.flush()
            emergency = Appointment(
                patient_id=patient.id, doctor_id=doctor.id, type_id=appt_type.id,
                scheduled_start=slot_start, scheduled_end=slot_end,
                status=AppointmentStatus.COMPLETED, origin=AppointmentOrigin.EMERGENCY,
                acuity=acuity, version=1,
            )
            db.add(emergency)
            db.flush()
            db.add(TriageAssessment(
                patient_id=patient.id, nurse_id=nurse.id, acuity=acuity,
                chief_complaint=complaint, vitals=vitals,
                assessed_at=created, consumed_at=created + timedelta(minutes=2),
            ))
            placement = {"doctor_id": doctor.id, "start": slot_start.isoformat(),
                         "end": slot_end.isoformat()}
            moves = ([{"appointment_id": moved.id, "from_start": slot_start.isoformat(),
                       "to_start": moved.scheduled_start.isoformat(),
                       "delay_min": int((moved.scheduled_start - slot_start).total_seconds()
                                        // 60)}] if moved is not None else [])
            decision = SchedulingDecision(
                trigger="emergency_insert", status="auto_committed",
                engine_version="cadence-demo-1.0", actor_id=nurse.id, patient_id=patient.id,
                emergency_appointment_id=emergency.id, idempotency_key=key,
                request_hash=hashlib.sha256(key.encode()).hexdigest(),
                input_snapshot={"patient_id": patient.id, "acuity": acuity.value,
                                "type_id": appt_type.id, "demo_record": True},
                chosen_plan={"placement": placement, "moves": moves},
                alternatives=[{"placement": placement, "moves": moves}],
                parameters={"max_displacements": 2, "max_auto_displaced": 3,
                            "max_auto_delay_min": 30},
                reasons=[f"priority_{acuity.value}_emergency_insertion"
                         if moves else "absorbed_by_open_time"],
                created_at=created + timedelta(minutes=3),
            )
            db.add(decision)
            db.flush()
            if moved is not None:
                db.add(AppointmentDisplacement(
                    appointment_id=moved.id, decision_id=decision.id, from_start=slot_start,
                    to_start=moved.scheduled_start,
                    reason=f"{acuity.value.upper()} emergency priority insertion",
                    created_at=created + timedelta(minutes=3),
                ))
            db.add(AuditLog(
                entity_type="scheduling_decision", entity_id=str(decision.id),
                action=AuditAction.CREATE.value, actor_id=nurse.id, before=None,
                after={"patient_id": patient.id, "emergency_appointment_id": emergency.id},
                reason="Demo seed: emergency insertion auto-committed",
                created_at=created + timedelta(minutes=3),
            ))
            db.add(AuditLog(
                entity_type="triage", entity_id=str(patient.id),
                action=AuditAction.CREATE.value, actor_id=nurse.id, before=None,
                after={"acuity": acuity.value, "chief_complaint": complaint},
                reason="Demo seed: triage assessment recorded", created_at=created,
            ))
        return 1
    except IntegrityError:
        log.info("Skipped a demo emergency on %s: schedule conflict", day)
        return 0


def _one_escalation(
    db: Session, rng: random.Random, day: date, nurses: list[User], admin: User,
    patients: dict[int, Patient], doctors: list[User], now: datetime,
) -> int:
    key = _key(day, 9)
    busy = set(db.scalars(select(SchedulingDecision.patient_id)))
    candidates = [p for pid, p in patients.items() if pid not in busy]
    if not candidates:
        return 0
    patient = candidates[rng.randrange(len(candidates))]
    nurse = nurses[day.toordinal() % len(nurses)]
    when = _at(day, time(rng.choice([11, 15, 17, 19]), rng.choice([5, 20, 40])))
    complaint = rng.choice([
        "Collapse with brief loss of consciousness",
        "Crushing chest pain with sweating; ST changes suspected",
        "Severe breathlessness, saturation falling",
    ])
    decision = SchedulingDecision(
        trigger="emergency_insert", status="escalated", engine_version="cadence-demo-1.0",
        actor_id=nurse.id, patient_id=patient.id, emergency_appointment_id=None,
        idempotency_key=key, request_hash=hashlib.sha256(key.encode()).hexdigest(),
        input_snapshot={"patient_id": patient.id, "acuity": "a1", "demo_record": True},
        chosen_plan=None,
        alternatives=[{"status": "clinician_reviewed", "label": "Resuscitation bay"}],
        parameters={"max_displacements": 2, "max_auto_displaced": 3, "max_auto_delay_min": 30},
        reasons=["a1_requires_clinician"], created_at=when,
        resolved_at=when + timedelta(minutes=rng.randint(4, 12)),
        resolved_by=admin.id, resolution_note=_RESOLUTIONS[day.toordinal() % len(_RESOLUTIONS)],
    )
    db.add(decision)
    db.flush()
    db.add(TriageAssessment(
        patient_id=patient.id, nurse_id=nurse.id, acuity=Acuity.A1, chief_complaint=complaint,
        vitals={"blood_pressure": "90/58", "heart_rate_bpm": 128, "temperature_c": 37.1,
                "oxygen_saturation_pct": 89},
        assessed_at=when - timedelta(minutes=2), consumed_at=when,
    ))
    db.add(AuditLog(
        entity_type="scheduling_decision", entity_id=str(decision.id),
        action=AuditAction.RESOLVE.value, actor_id=admin.id, before={"status": "escalated"},
        after={"resolution_note": decision.resolution_note},
        reason="Demo seed: escalation resolved", created_at=decision.resolved_at or when,
    ))
    return 1


# --------------------------------------------------------------------------------------------
# Patient messages for every displacement
# --------------------------------------------------------------------------------------------


def ensure_notifications(db: Session) -> int:
    """Every displaced patient has a message record ("Logged (demo)" unless Twilio is on)."""
    provider = settings.notify_provider.lower()
    if provider == "off":
        return 0
    have = {(a, d) for a, d in db.execute(
        select(Notification.appointment_id, Notification.decision_id))}
    made = 0
    for disp in db.scalars(select(AppointmentDisplacement).order_by(AppointmentDisplacement.id)):
        if (disp.appointment_id, disp.decision_id) in have:
            continue
        appt = db.get(Appointment, disp.appointment_id)
        if appt is None:
            continue
        phone = extract_phone(appt.patient.contact)
        sent_at = _utc(disp.created_at) + timedelta(seconds=40)
        db.add(Notification(
            patient_id=appt.patient_id, appointment_id=appt.id, decision_id=disp.decision_id,
            kind="appointment_moved", channel=settings.notify_channel if phone else "none",
            provider=provider, recipient=phone,
            body=moved_message(appt, _utc(disp.from_start), _utc(disp.to_start),
                               "because a medical emergency had to be seen"),
            status="sent" if phone else "skipped",
            error=None if phone else "No phone number on file",
            provider_ref=f"console-demo-{disp.id}" if phone and provider == "console" else None,
            attempts=1 if phone else 0, created_at=_utc(disp.created_at),
            sent_at=sent_at if phone else None,
        ))
        made += 1
    return made
