# Cadence synthetic demo dataset

Cadence can start with a populated, fictional hospital workload so the dashboard and the
other modules can be demonstrated without manually entering every record. The seed is for
product demonstrations and automated tests only. It is not real patient information and is
not suitable for clinical use.

## Seed contents

The PostgreSQL seed (`backend/app/seed.py`) creates or refreshes:

- **64 fictional patients** with Indian-style names, medical-record numbers, dates of birth,
  mobile numbers, cities, blood groups, emergency contacts and short notes.
- **11 staff accounts**, including two receptionists, two triage nurses, six doctors and the
  administrator account `admin@cadence.dev` (display name: Saurabh Raj Shekhar).
- **Five specialties across six doctors**: general medicine (two doctors), cardiology,
  paediatrics, orthopaedics and dermatology.
- **14 days of doctor shifts**, split into 09:00–13:00 and 14:00–22:00 clinic sessions in
  `CADENCE_CLINIC_TIMEZONE` (Asia/Kolkata by default).
- **A populated schedule**: around 120 appointments on a fresh database, with completed visits,
  a no-show example, active consultations, waiting/check-in patients at different acuity levels,
  and bookings on the next six days. The exact count varies with the current clinic time and
  any existing appointments in the demo patients' schedules.
- **Clinical-flow examples**: synthetic nurse triage records across A1–A5, an A2 emergency
  insertion with a 30-minute displacement, one unresolved A1 escalation that requires
  clinician direction, and one resolved historical escalation.
- **Audit activity** for patient registrations, appointment creation/status examples, triage
  entries and scheduling decisions.

The seeded patients are grouped into small panels for each doctor. The additional emergency
and displacement examples use dedicated demo patients, so they do not collide with the
ordinary daily appointment panels. The daily appointment generator uses the current clinic
clock and avoids the 13:00–14:00 lunch closure. A rolling six-day booking horizon keeps the
calendar useful after the first deployment.

When MongoDB is configured, `backend/app/seed_profiles.py` adds structured patient and staff
profile sections (addresses, language, emergency contacts, reported conditions/allergies,
insurance, staff registration, qualifications and role-specific details). Without MongoDB,
the core scheduling, patient list, triage, dashboard, history and audit data still work from
PostgreSQL alone.

## Enable seeding on Render or another host

Set the following backend environment variables:

```dotenv
CADENCE_SEED_DEMO_ON_START=true
CADENCE_SEED_PASSWORD=<a strong private password for demo accounts>
CADENCE_CLINIC_TIMEZONE=Asia/Kolkata
```

`CADENCE_SEED_PASSWORD` is required when `CADENCE_ENV=production`. Every seeded account uses
that configured password; do not put the production value in source control, screenshots or
public documentation. Setting it also rotates passwords for accounts managed by the seed.

After deploying the updated backend, the API startup hook runs the seed. Render's Environment
page should show `CADENCE_SEED_DEMO_ON_START=true`; once the new deployment is **Live**, sign
out and back in, then refresh the dashboard. No manual SQL insert is needed.

## Idempotency and safety

The seed uses stable staff emails, patient MRNs, patient/day appointment checks, and
per-day scheduling-decision keys. Re-running it updates the seed-owned staff/patient/shift
records in place and creates only missing demo appointments, triage entries, decisions and
audit records. It does not truncate tables or delete patients registered through the app.

The demo schedule is intentionally synthetic and should only be enabled in an isolated demo
or development environment. Before using Cadence with real hospital operations, turn off
`CADENCE_SEED_DEMO_ON_START`, remove the synthetic dataset through a planned database cleanup,
and validate the workflows with the hospital's authorised clinical and data-governance teams.

## Local run

From the repository root:

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.seed
```

The local-only default password is `cadence123`. Production deployments must use
`CADENCE_SEED_PASSWORD` instead.

## How the seed behaves over time

The seed runs on every start when `CADENCE_SEED_DEMO_ON_START=true`, and the demo is meant to
look "live" on any day. These rules keep that true; please keep them if you edit the seed:

- **The clock moves, the data follows.** Appointments are re-anchored to the current clinic
  time; demo triage assessments from an earlier day are re-dated (a same-day restart leaves
  them alone, so anything a clinician did that day survives).
- **The pending A1 escalation is created by the real planner** (`plan_emergency` +
  `commit_emergency`), never hand-written, so *Review options* shows genuine, applicable plans.
  Unresolved demo escalations from earlier days (or any with malformed options) are removed so
  the inbox never piles up. Resolved ones are kept as history.
- **Someone is always in consultation while the clinic is open** (09:00–13:00 and 14:00–22:00
  IST; 13:00–14:00 is the lunch closure). Before opening and late in the evening the day's
  patients are simply waiting or completed.
- **Passwords are hashed at most once per run**, and not at all on a restart if the demo
  password is unchanged (hashing is deliberately slow and would dominate a free host's cold
  start). Changing `CADENCE_SEED_PASSWORD` rotates every demo account on the next start.
- **MongoDB profiles are filled only where missing**, so edits made in the app survive restarts.
  The one exception is filler written by older seeds ("Demo family contact…", "Demo residence…",
  occupation "Not recorded"), which is replaced with realistic values.
