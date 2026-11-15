# Improvements round 3

| # | Feature | Where |
|---|---|---|
| 1 | **Emergency reserve** - each shift holds N x M-minute blocks back from routine booking; only the emergency engine may use them. `GET /doctors/{id}/emergency-reserve?day=` lists them. | `scheduling/availability.py::reserved_blocks`, `services/scheduling.py` |
| 2 | **Patient notifications** - an outbox row is written in the same transaction as every displacement, delivered after commit (console demo or Twilio SMS/WhatsApp), retryable. UI: **Notifications** page. | `services/notifications.py`, `api/notifications.py`, migration `0009` |
| 3 | **Consultation overrun** - `POST /appointments/{id}/extend {minutes}` lengthens the in-progress consult and ripples later patients forward only as far as needed (gaps absorb it; lunch/shift end respected). All-or-nothing; recorded as a `consult_overrun` decision with displacements, audit and notifications. UI: "Running over? +10 / +20 min" on the Queue page. | `services/overrun.py` |
| 4 | **Re-plan prompt** - when applying an escalation option is refused because the schedule changed or the plan expired, the review dialog now offers *Re-plan* right there. | `frontend/src/routes/DashboardPage.tsx` |
| 5 | **Seeded-demo flow test** - the seeded demo is run through triage -> plan -> commit at three times of day, checking safety invariants (no overlaps, fairness cap, idempotent replay, one notification per displaced patient). | `backend/tests/test_improvements.py` |

Notes: notifications default to the `console` provider, so "sent" messages are only logged
(the UI labels them "Logged (demo)"). Evening demo runs escalate more often because the engine
refuses to bump sicker patients for a lower-acuity emergency (`priority_inversion`).
