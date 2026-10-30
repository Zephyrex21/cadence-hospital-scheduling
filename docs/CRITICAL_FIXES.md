# Critical fixes (review round)

Every item below has a regression test in `backend/tests/test_critical_fixes.py`
(and, for the timeline, `frontend/src/features/schedule/timeline.test.ts`).
The backend suite also runs on real PostgreSQL: set `CADENCE_TEST_DATABASE_URL`.

| # | Problem found | Fix |
|---|---------------|-----|
| 1 | **Double-booking was possible** (check-then-insert race; no DB constraint). 8 concurrent requests all got the same slot. | PostgreSQL exclusion constraints (doctor **and** patient, active statuses) + equivalent SQLite triggers; per-doctor advisory locks; services map the violation to a clean 409. Ripple moves are written last-to-first so no intermediate state overlaps. |
| 2 | **A1 / escalated emergencies could never be scheduled** (resolve only stored a note; options were display-only). | `GET /escalations/{id}/options` + `POST /escalations/{id}/apply` (nurse/admin). The option is **recomputed against the live schedule** and must match exactly; dashboard "Review options" UI. |
| 3 | **A patient could be placed in two rooms** (ripple ignored their appointments with other eligible doctors). | Engine now counts the patient's other-doctor appointments as busy and forbids overlap with their own; DB constraint backs it up. |
| 4 | **UTC-midnight blind spot** (engine/booking only saw one UTC calendar day). | Rolling planning horizon (-12h / +36h) in the engine; booking checks the candidate's own time range. |
| 5 | **Server trusted a client clock** (`now`); plan-age check was one-sided; emergencies could start in the past. | Server clock is authoritative (`CADENCE_ALLOW_CLIENT_NOW`, test-only, refused in production). Commit recomputes and compares a `plan_digest` of what the reviewer saw. |
| 6 | **One triage authorised unlimited emergency inserts.** | `triage_assessments.consumed_at`: one assessment, one emergency. |
| 7 | **Idempotency key not bound to its request** (reuse returned another patient's result; concurrent duplicates -> 500). | `request_hash` stored with the key; mismatch -> 409; concurrent duplicate -> replay of the winner. |
| 8 | **Known JWT secret in a public repo, no production guard.** | No default secret: random per-process in dev, startup refuses weak/missing secret in production. |
| 9 | **Demo credentials, no brute-force protection.** | `CADENCE_SEED_PASSWORD` (required in prod, rotates existing accounts); login throttle (429 + Retry-After). Seed now creates 14 days of shifts. |
| 10 | **`FOR UPDATE` crashed on PostgreSQL** (found by running the suite on Postgres): check-in/start/complete/cancel and emergency commit failed with "nullable side of an outer join". | Lock only the `appointments` rows (`of=Appointment`). |
| 12 | **Dashboard "Could not load" on the live site**: new code deployed but the database never received the new column (no shell on Render's free tier). | The API now runs `alembic upgrade head` on startup (advisory-locked, fails fast on error); migration 0005 cancels — never deletes — any pre-existing overlapping appointments so it can't block the deploy. |
| 13 | Free-tier cold start looked like a broken site. | `BackendWakeBanner`: explains the free-hosting delay, polls `/health`, shows "Welcome" when awake, then fades out; failed first requests are refetched automatically. |
| 11 | Frontend: only the first 50 patients selectable; session expiry left the UI "signed in"; night/late appointments invisible on the timeline. | Searchable `PatientPicker`; `cadence:auth-expired` event logs out; timeline window widens to fit all appointments. |

Not changed (out of scope for "critical"): read access for non-admin roles, UTC display
for non-UTC clinics, notification of displaced patients, consultation overrun handling.
