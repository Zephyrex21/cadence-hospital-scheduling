# Cadence — Clinical Flow Platform

Dynamic, priority-aware appointment scheduling for public hospitals under resource
contention and walk-in emergency interruptions.

> **Synthetic demo data only — not for clinical use.** Cadence is a scheduling and
> operations tool. It is **not** a diagnostic or clinical-decision system. Triage acuity
> is always recorded by a human nurse; the engine only arranges time and resources.

## Status — feature complete

All eight blueprint phases are implemented and verified (backend `ruff` + `mypy` + `pytest`,
frontend `tsc` + `eslint` + `vitest`, a production build, and a Playwright end-to-end run of
the signature flow).

### What it does

- **Pure scheduling engine** — a bounded greedy cascade that inserts an emergency by
  rippling later appointments, enforcing hard safety/fairness constraints above a transparent
  cost function. Deterministic and fully auditable (every decision keeps its input snapshot,
  chosen plan, alternatives, parameters, and reasons).
- **Walk-in / emergency workflow** — nurse triage (acuity A1–A5), a **plan → commit** split
  with a state fingerprint + idempotency key so a stale or double-clicked commit is safe,
  automatic application only when the engine auto-approves, and escalation to a clinician
  otherwise. Acuity is **enforced server-side** — plan/commit are refused unless the patient has a
  recent triage (last 12 h) whose acuity matches the request (receptionists see the nurse's recorded
  acuity read-only); a reviewed plan older than 10 minutes is rejected so it can be re-planned.
  In-progress consultations are never displaced, and no patient is placed into two overlapping
  appointments.
- **Booking** — fits an appointment inside a doctor's shift with no double-booking; rejects times in
  the past (and hides past slots) and rejects a patient already booked over that time.
- **Priority queue** with wait estimates, and doctor consultation-status management
  (check-in → start → complete / no-show).
- **History & oversight** — a displacements register, per-decision trace viewer, and an
  append-only audit log (admin only).
- **Operational dashboard** — live workload tiles, waiting-by-acuity, per-doctor running
  delay, and an **escalation inbox** that lists every *unresolved* escalation (any day) with a
  Resolve action (nurse / administrator, note required — recorded to the audit log).
- **Polished, premium UI** ("Clinical Calm 2.0") — light **and dark** mode (system default,
  persisted), self-hosted variable fonts, frosted-glass shell/modals, purposeful motion
  (count-up tiles, animated schedule/queue, an emergency before/after mini-timeline), a custom
  inline-SVG illustration set, and one restrained 3D hero on the login screen. Responsive
  (mobile drawer), keyboard-accessible, WCAG-AA, and fully `prefers-reduced-motion` safe. See
  [docs/UI_JOURNAL.md](docs/UI_JOURNAL.md).

## Stack

| Layer    | Choice                                                        |
| -------- | ------------------------------------------------------------- |
| Frontend | React 18 + Vite + TypeScript, Tailwind CSS v3, TanStack Query |
| Backend  | Python 3.11+ + FastAPI, SQLAlchemy 2.0, Alembic               |
| Database | PostgreSQL (prod) / SQLite (zero-setup local + tests)         |
| BE tests | pytest · ruff · mypy (strict)                                 |
| FE tests | Vitest + Testing Library · ESLint · tsc                       |
| E2E      | Playwright                                                    |

## Prerequisites

- **Python 3.11+** with [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- **Node.js 20+** with [`pnpm`](https://pnpm.io/) (recommended) or `npm`
- **Docker** — optional, only for the PostgreSQL path below

## Quick start (no Docker — SQLite)

The fastest way to run and click through the whole app. Two terminals.

### 1. Backend → http://localhost:8000

```bash
cd backend

# Tell the app to use a local SQLite file instead of PostgreSQL.
#   macOS / Linux / Git Bash:
echo 'CADENCE_DATABASE_URL=sqlite+pysqlite:///./cadence.db' > .env
#   Windows PowerShell:
#   Set-Content .env 'CADENCE_DATABASE_URL=sqlite+pysqlite:///./cadence.db'

uv sync --extra dev                       # install dependencies
uv run alembic upgrade head               # create the schema
uv run python -m app.seed                 # load synthetic demo data (idempotent)
uv run uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs · health: http://localhost:8000/health

<details>
<summary>Using <code>pip</code> instead of <code>uv</code></summary>

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```
(Set `CADENCE_DATABASE_URL` via the `.env` file as above.)
</details>

### 2. Frontend → http://localhost:5173

```bash
cd frontend
pnpm install        # or: npm install
pnpm run dev        # or: npm run dev
```

Open **http://localhost:5173** and sign in. The dev server proxies `/api/*` to the backend.

### Demo accounts (all password `cadence123`)

| Email                     | Role          | Can do                                      |
| ------------------------- | ------------- | ------------------------------------------- |
| `admin@cadence.dev`       | Administrator | everything, incl. Decisions & audit         |
| `nurse@cadence.dev`       | Triage nurse  | triage, book, emergency plan/commit, queue   |
| `receptionist@cadence.dev`| Receptionist  | book, emergency plan/commit                  |
| `doctor@cadence.dev`      | Doctor        | manage own consultations (queue status)      |

Sign in as **admin** to see the full product in one account.

## Alternative: PostgreSQL via Docker

```bash
docker compose up -d db          # starts PostgreSQL 16 on :5432
cd backend
uv sync --extra dev              # (no .env needed — the default URL points here)
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

## Verifying it works (the full check suite)

```bash
# Backend
cd backend
uv run ruff check .
uv run mypy app
uv run pytest -q

# Frontend
cd frontend
pnpm run typecheck
pnpm run lint
pnpm test
pnpm run build
```

Or run everything at once from the repo root: `bash checkup.sh` (writes results to `checkup.log`).

### End-to-end test (Playwright)

Boots the backend (throwaway SQLite) + the frontend and drives the signature flow —
sign in → book → triage + emergency → commit (displacing a booked patient) → see the
displacement → read the decision & audit — in a real browser.

```bash
cd frontend
pnpm exec playwright install chromium   # one-time: download the browser
pnpm run e2e
```

## Project layout

```
.
├── backend/                 FastAPI modular monolith
│   ├── app/
│   │   ├── api/             routers (auth, patients, scheduling, emergency,
│   │   │                     consultation, history, dashboard, health)
│   │   ├── core/            config, db, security, errors, enums, deps
│   │   ├── models/          SQLAlchemy ORM models
│   │   ├── schemas/         Pydantic request/response models
│   │   ├── scheduling/      pure engine + availability/queue/dashboard logic
│   │   ├── services/        transactional business logic
│   │   ├── seed.py          synthetic demo data
│   │   └── e2e_seed.py/e2e_server.py   deterministic data + launcher for the E2E
│   ├── alembic/             database migrations
│   └── tests/               pytest suite
├── frontend/                React + Vite + TypeScript
│   ├── src/
│   │   ├── components/      shared UI (Modal, states, AppShell, …)
│   │   ├── features/        auth, patients, schedule, queue, emergency,
│   │   │                     history, dashboard (api + components + unit tests)
│   │   ├── routes/          page components
│   │   └── styles/          "Clinical Calm" design tokens
│   └── e2e/                 Playwright signature-flow spec
├── docker-compose.yml       PostgreSQL
├── checkup.sh               one-shot full check (backend + frontend)
└── .github/workflows/       CI
```

## Notes

- All timestamps are stored in **UTC**; `CADENCE_CLINIC_TIMEZONE` is for display only.
- Configuration is via environment variables prefixed `CADENCE_` (see `.env.example`),
  read from a `backend/.env` file if present.
- The seed is idempotent — safe to re-run.

## License

Private project — educational / portfolio use.
