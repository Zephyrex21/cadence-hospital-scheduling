# Cadence — Clinical Flow Platform

Dynamic, priority-aware appointment scheduling for public hospitals under resource
contention and walk-in emergency interruptions.

> **Fictitious demo data only — not for clinical use.** Cadence is a scheduling and
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
  acuity read-only). The **server clock is authoritative** (a client-supplied `now` is ignored
  outside tests), commit recomputes the plan and refuses it if it no longer matches the
  `plan_digest` the reviewer saw, and **one triage authorises exactly one emergency**.
  In-progress consultations are never displaced, and no patient is placed into two overlapping
  appointments — across *all* doctors, enforced by the database itself (see below).
- **Escalations are actionable** — A1 and any plan the engine will not auto-apply are recorded and
  appear in the dashboard inbox. A nurse/administrator can **Review options** and **Apply** one:
  the chosen option is re-validated against the live schedule (all hard constraints re-checked)
  before it is written, so a stale option is refused rather than applied.
- **Booking** — fits an appointment inside a doctor's shift with **no double-booking, guaranteed by
  the database** (PostgreSQL exclusion constraints; equivalent triggers on SQLite) for both the
  doctor and the patient, plus per-doctor advisory locks on PostgreSQL so concurrent requests
  queue instead of racing; rejects times in the past (and hides past slots).
- **Priority queue** with wait estimates, and doctor consultation-status management
  (check-in → start → complete / no-show).
- **History & oversight** — a displacements register, per-decision trace viewer, and an
  append-only audit log (admin only).
- **Operational dashboard** — live workload tiles, waiting-by-acuity, per-doctor running
  delay, and an **escalation inbox** that lists every *unresolved* escalation (any day) with a
  Resolve action (nurse / administrator, note required — recorded to the audit log).
- **Apple-inspired premium UI** ("Cream & Moon") — a warm **cream** light theme with a soft
  shine and a **moon-black** dark theme (light / system / dark, persisted, no flash on load), one
  Apple-blue accent, frosted-glass floating sidebar and top bar, SF-style type (real SF Pro on
  Apple devices, Inter elsewhere), Phosphor icons, a lightweight animated login hero (no WebGL),
  and purposeful motion that respects `prefers-reduced-motion`. Responsive, keyboard-accessible,
  and WCAG-AA — enforced by an automated contrast test over every text/background token pair in
  both themes. See [docs/REDESIGN.md](docs/REDESIGN.md).
- **Built for an Indian clinic** — all times shown in **IST** (12-hour clock, day-first dates,
  en-IN number grouping); "today", the schedule day and the queue day follow the clinic timezone;
  Indian demo staff, doctors and patients; and a richer patient record (mobile, city, blood
  group, emergency contact, notes) that accepts any name, including Devanagari.

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
uv run python -m app.seed                 # load the Indian demo data (idempotent)
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

### Demo accounts (local development only — password `cadence123`)

> The well-known demo password exists **only for local development**. Anywhere real, set
> `CADENCE_SEED_PASSWORD` before seeding — it is *required* when `CADENCE_ENV=production`, and
> re-running the seed with it set **rotates the password of already-seeded accounts**.

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
│   │   ├── seed.py          Indian demo data (idempotent upserts)
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

## Security & deployment checklist

- **`CADENCE_JWT_SECRET`** — there is no built-in default. Outside production, an unset secret
  becomes a random per-process one (sessions end on restart). With `CADENCE_ENV=production` the
  app **refuses to start** unless it is set to a random value of at least 32 characters
  (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- **`CADENCE_SEED_PASSWORD`** — required to seed in production; use a strong, unique value.
- **`CADENCE_ALLOW_CLIENT_NOW`** — test/E2E only (pins the clock); must stay off in production
  (startup fails if enabled there).
- **Login throttling** — repeated failed sign-ins per client/email are rejected with `429` +
  `Retry-After` (`CADENCE_LOGIN_MAX_ATTEMPTS`, `CADENCE_LOGIN_WINDOW_SEC`). The throttle is
  in-process; use a shared store if you run several API instances.
- **Migrations run automatically.** The API applies `alembic upgrade head` on startup
  (`CADENCE_AUTO_MIGRATE`, default on; a PostgreSQL advisory lock makes concurrent instances take
  turns). Deploying new code therefore never needs a manual migration step — useful on hosts with
  no shell, such as Render's free tier. If a migration fails the app refuses to start, so the host
  keeps serving the previous release instead of running against a mismatched schema.
- **Upgrading an existing database** — migration `0005` adds the overlap guards. On PostgreSQL it
  creates the `btree_gist` extension (allowed for the database owner on managed Postgres). Any
  *pre-existing* overlapping active appointments are invalid by definition, so the migration keeps
  the earliest-created one and marks the later ones `cancelled` (never deleted) and logs their ids.
  If the live database was seeded with the old demo password, run
  `CADENCE_SEED_PASSWORD=<strong> python -m app.seed` once to rotate it.
- **Free-tier hosting.** On Render's free plan the API sleeps when idle. The UI shows a
  "waking up the server" notice, polls `/health`, says "Welcome" when it's awake, then disappears.
  Set `CADENCE_JWT_SECRET` so sign-ins also survive the server restarting.

## Notes

- All timestamps are stored in **UTC**. `CADENCE_CLINIC_TIMEZONE` (default `Asia/Kolkata`) decides
  what "today" means on the backend; the UI formats everything in IST via `src/lib/time.ts`.
- **Refreshing the demo data on a host with no shell** (e.g. Render free tier): set
  `CADENCE_SEED_DEMO_ON_START=true` (and `CADENCE_SEED_PASSWORD` in production) and redeploy. It
  runs the idempotent seed at startup: existing demo records are updated *in place* (old
  placeholder names become the Indian ones), past unattended demo appointments are closed out,
  new sample appointments are placed in the future, and patients you registered are untouched.
- Configuration is via environment variables prefixed `CADENCE_` (see `.env.example`),
  read from a `backend/.env` file if present.
- The seed is idempotent — safe to re-run. It creates shifts for the next 14 days, so a
  long-lived demo does not run out of availability.
- Run the whole backend suite against a real PostgreSQL with
  `CADENCE_TEST_DATABASE_URL=postgresql+psycopg://… pytest` (the concurrency tests run there).

## License

Private project — educational / portfolio use.
