"""Patient notifications: queue a message when an appointment moves, deliver it, retry it.

Messages are written to an outbox inside the caller's transaction (``queue_moved``); delivery
(``dispatch_queued``) runs after that transaction commits and can never fail the request that
triggered it. A provider outage leaves rows ``failed`` for a human to retry.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.models.base import ensure_aware_utc, utcnow
from app.models.notification import Notification
from app.models.patient import Patient

_log = logging.getLogger("cadence.notify")

KIND_MOVED = "appointment_moved"
_SEND_TIMEOUT_SEC = 5
_MAX_ATTEMPTS = 5


def extract_phone(contact: str | None) -> str | None:
    """The first usable phone number in a free-text contact, as E.164, or None.

    E-mail addresses are not phones. Numbers without a ``+`` get the clinic's country code
    (10 digits, or 11 with a leading 0).
    """
    if not contact or "@" in contact:
        return None
    first = re.split(r"[/,;]", contact)[0].strip()
    digits = re.sub(r"\D", "", first)
    cc = re.sub(r"\D", "", settings.notify_default_country_code)
    if first.startswith("+"):
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return f"+{cc}{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"+{cc}{digits[1:]}"
    if len(digits) == 12 and digits.startswith(cc):
        return f"+{digits}"
    return None


def mask_phone(phone: str | None) -> str | None:
    return None if not phone else f"{phone[:3]}{'•' * max(len(phone) - 7, 2)}{phone[-4:]}"


def _when(value: datetime) -> str:
    local = ensure_aware_utc(value).astimezone(settings.clinic_tz)
    return local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def moved_message(appt: Appointment, from_start: datetime, to_start: datetime, why: str) -> str:
    return (
        f"Cadence: your appointment with {appt.doctor.name} has moved from {_when(from_start)} "
        f"to {_when(to_start)} {why}. We apologise for the change; call the front desk if "
        "this time doesn't work for you."
    )[:600]


def queue_moved(
    db: Session,
    appt: Appointment,
    *,
    from_start: datetime,
    to_start: datetime,
    decision_id: int | None,
    reason: str,
) -> Notification | None:
    """Add an outbox row (no commit). ``reason`` is "emergency" or "overrun"."""
    if settings.notify_provider.lower() == "off":
        return None
    why = (
        "because a medical emergency had to be seen"
        if reason == "emergency"
        else "because the earlier consultation is running over"
    )
    patient: Patient = appt.patient
    phone = extract_phone(patient.contact)
    channel = "none" if phone is None else settings.notify_channel
    row = Notification(
        patient_id=patient.id,
        appointment_id=appt.id,
        decision_id=decision_id,
        kind=KIND_MOVED,
        channel=channel,
        provider=settings.notify_provider.lower(),
        recipient=phone,
        body=moved_message(appt, from_start, to_start, why),
        status="queued" if phone else "skipped",
        error=None if phone else "No phone number on file",
    )
    db.add(row)
    return row


@dataclass
class SendResult:
    ok: bool
    ref: str | None = None
    error: str | None = None


def _send_console(row: Notification) -> SendResult:
    _log.info("[demo notification -> %s via %s] %s", row.recipient, row.channel, row.body)
    return SendResult(True, ref=f"console-{row.id}")


def _send_twilio(row: Notification) -> SendResult:
    sid, token = settings.twilio_account_sid, settings.twilio_auth_token
    whatsapp = row.channel == "whatsapp"
    sender = settings.twilio_whatsapp_from if whatsapp else settings.twilio_sms_from
    if not (sid and token and sender and row.recipient):
        return SendResult(False, error="Twilio is not fully configured")
    to = f"whatsapp:{row.recipient}" if whatsapp else row.recipient
    data = urllib.parse.urlencode({"To": to, "From": sender, "Body": row.body}).encode()
    request = urllib.request.Request(  # noqa: S310 - fixed https URL
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=data,
        method="POST",
    )
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    request.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(request, timeout=_SEND_TIMEOUT_SEC) as resp:  # noqa: S310
            body: dict[str, Any] = json.loads(resp.read().decode() or "{}")
        return SendResult(True, ref=str(body.get("sid", ""))[:80] or None)
    except urllib.error.HTTPError as exc:
        return SendResult(False, error=f"Twilio rejected the message (HTTP {exc.code})")
    except Exception as exc:  # network down, timeout, bad JSON ...
        return SendResult(False, error=f"{type(exc).__name__}: {exc}"[:255])


def _deliver(row: Notification) -> SendResult:
    try:
        if row.provider == "twilio":
            return _send_twilio(row)
        return _send_console(row)
    except Exception as exc:  # a provider bug must never escape
        return SendResult(False, error=f"{type(exc).__name__}: {exc}"[:255])


def dispatch_queued(db: Session, *, limit: int = 25) -> int:
    """Deliver queued notifications; returns how many were sent. Never raises."""
    try:
        rows = list(
            db.scalars(
                select(Notification)
                .where(Notification.status == "queued")
                .order_by(Notification.id)
                .limit(limit)
            )
        )
        sent = 0
        for row in rows:
            result = _deliver(row)
            row.attempts += 1
            if result.ok:
                row.status, row.error, row.provider_ref, row.sent_at = (
                    "sent", None, result.ref, utcnow(),
                )
                sent += 1
            else:
                row.status, row.error = "failed", result.error
        db.commit()
        return sent
    except Exception:
        _log.exception("Notification dispatch failed")
        db.rollback()
        return 0


def list_notifications(
    db: Session, *, status: str | None = None, limit: int = 100
) -> list[tuple[Notification, Patient]]:
    stmt = select(Notification, Patient).join(Patient, Patient.id == Notification.patient_id)
    if status:
        stmt = stmt.where(Notification.status == status)
    rows = db.execute(
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    ).all()
    return [(n, p) for n, p in rows]


def retry_notification(db: Session, notification_id: int) -> Notification:
    row = db.get(Notification, notification_id)
    if row is None:
        raise NotFoundError("Notification not found")
    if row.status not in ("failed", "queued"):
        raise ValidationError(f"A {row.status} notification can't be retried")
    if row.attempts >= _MAX_ATTEMPTS:
        raise ValidationError("This notification has failed too many times; contact the patient")
    row.status = "queued"
    db.commit()
    dispatch_queued(db)
    db.refresh(row)
    return row
