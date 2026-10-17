# Cadence UI Redesign — Journal

"Clinical Calm 2.0" — a frontend-only redesign for premium, production-grade polish while
staying a fast, calm clinical operations tool. Frontend only; backend, API contracts, and
business logic (`src/lib`, `features/*/api.ts`, `format.ts`, `schema.ts`, `timeline.ts`
geometry) are untouched.

## Baseline (before)
- `vite build`: JS **360 KB raw / 107 KB gzip**, CSS 19.67 KB / 4.57 KB gzip.
- Tokens were already clean (no hardcoded colors in components). Dark tokens existed but nothing
  toggled `.dark`. Fonts (Inter/Geist) were declared in Tailwind but never loaded. Acuity dots
  used a dynamic `bg-acuity-${n}` class that Tailwind's JIT purged (dots were invisible).

## Phase 1 — Foundation (tokens, fonts, dark mode, motion, primitives)

### Decisions
- **Dependencies** (verified on npm before install; versions pinned for React 18):
  `framer-motion@11.18.2`, `three@0.169.0` (+ `@types/three@0.169.0`), `@react-three/fiber@8.18.0`
  (peer `react >=18 <19`), `@react-three/drei@9.122.0` (peer `react ^18`, `fiber ^8`),
  `@fontsource-variable/inter@5.3.0`, `@fontsource-variable/geist@5.3.0`. pnpm did **not** block any
  build scripts. three pinned to 0.169 (not latest 0.186) to stay on a combo well-tested with fiber v8.
- **Fonts self-hosted, not CDN:** copied the latin variable `woff2` from the `@fontsource-variable`
  packages into `public/fonts/{inter,geist}-variable.woff2`, declared via `@font-face`
  (`font-display: swap`, `font-weight: 100 900`) in `src/styles/fonts.css`, and preloaded in
  `index.html`. This gives genuine preload with no Vite hashing and no layout shift.
- **Bug fixes:** (A) acuity classes safelisted in `tailwind.config.ts` (`^(bg|text|ring|border)-acuity-[1-5]$`)
  so the dynamic `acuityDotClass()` in the off-limits `format.ts` finally renders. (B) fonts now load.
- **Dark mode:** `src/theme/ThemeProvider.tsx` (system | light | dark, persisted in
  `localStorage['cadence.theme']`), with an inline no-flash script in `index.html` that sets `.dark`
  before first paint. Lives outside `src/lib` (which is off-limits).
- **Motion:** `src/motion.ts` central module (durations 150/250/400, easings, springs, stagger,
  variants). App wrapped in `MotionConfig reducedMotion="user"` + `LazyMotion` (features loaded lazily)
  so motion stays ~small in the initial bundle.

### Contracts kept green
- `Modal.test.tsx`: role=dialog, aria-modal, accessible name, Escape, "Close dialog", backdrop =
  panel's direct parent, scroll lock. `StatusBadge.test.tsx`. The Playwright signature-flow selectors/text.

### Verification (actual results)
- `pnpm run typecheck` → **0 errors**.
- `pnpm run lint` → **0 errors**.
- `pnpm test` → **30 passed** (8 files); Modal + StatusBadge contracts intact.
- `pnpm run build` → OK. **Initial/entry JS = 117 KB gzip** (`index.html` loads only the entry
  chunk; the 41 KB framer-motion feature set is a separate on-demand chunk, no modulepreload) —
  under the 200 KB budget (baseline 107 KB, +10 KB for static motion core). CSS 5.8 KB gzip. Fonts
  preloaded.
- `pnpm run e2e` → **1 passed** (signature flow unchanged).
- Screenshots captured at 1440 & 390, light & dark (`e2e-shots/`). Self-review: acuity dots now
  render (bug A fixed); fonts load (bug B fixed); dark mode cohesive across shell/cards/tables/forms;
  teal button `text-surface` flip keeps contrast in both themes. Fix applied during review: placed
  the `ThemeToggle` in the sidebar footer so dark mode is user-togglable (it was built but unplaced).

### Deferred to later phases (as planned)
- 🎉 emoji on the dashboard escalation inbox → removed in Phase 2 (dashboard redesign).
- Primitives (Select/Card/Tabs/Toast/Tooltip/Skeleton) are built but not yet wired into every
  screen; screen adoption happens in Phases 2–3. Existing screens stay backward-compatible.

## Phases 2–4 (implemented in one pass, verified together)

### Phase 2 — Shell + Login (3D) + Dashboard
- **AppShell**: frosted (`backdrop-blur`) collapsible sidebar (collapse persisted in
  `localStorage`) with a **shared-`layoutId` animated active indicator**; a top bar with a live UTC
  **clinic clock**, the synthetic-data notice as a **pill** (tooltip holds the full text), the
  `ThemeToggle` (moved here from the footer), and a **user menu** (click-outside + Escape). Mobile
  drawer retained; distinct `layoutId`s for sidebar vs drawer avoid a shared-layout conflict.
- **Login**: split-screen. The **3D hero** (`src/features/login/Hero3D.tsx`) is an R3F scene of
  translucent frosted "time blocks" with one accent block gliding into the day, pointer parallax,
  DPR ≤ 1.5, render loop paused when the tab is hidden — **lazy-loaded** (`React.lazy`) so three.js
  lands in its own chunk. Falls back to a static CSS/SVG hero on reduced-motion, no-WebGL, or < lg.
- **Dashboard**: staggered entrance (`m` + stagger variants), **count-up** tiles (reduced-motion
  safe), an **acuity distribution bar** + legend, and a calm **illustration** empty state — the
  🎉 emoji is gone.

### Phase 3 — Schedule + Queue + Emergency
- **ScheduleTimeline**: a live **"now" line**, **focus/hover detail cards** rendered in a portal
  (so they aren't clipped by the scroll container), in-progress **glow**, and block entrance motion.
  Geometry reused from the off-limits `timeline.ts` unchanged. **SchedulePage** gains prev/next day
  navigation + a Today shortcut.
- **Queue**: animated **reorder** (`m.li layout` + `AnimatePresence`), clearer priority rows, and
  larger wait-estimate typography.
- **Emergency**: a **Triage → Review → Commit stepper** (every e2e label/button/text preserved:
  Patient / Appointment type / Chief complaint selects, "Review plan", "Commit schedule",
  "Emergency scheduled. 1 appointment rescheduled."). **PlanReview** gains an animated
  **before/after mini-timeline** — displaced blocks glide from their old slot to the new one
  (reduced-motion safe). Restrained success moment (no confetti).

### Phase 4 — Tables, illustrations, a11y + perf
- **Tables** (Displacements / Audit / Patients): sticky headers, internal scroll, row hover, Card
  framing. A **404** page. A custom inline-SVG **illustration set** (calm / empty-list / calendar /
  404 / error) powering empty and error states (dark-aware, subtle idle motion, reduced-motion safe).
- **a11y**: visible focus rings throughout; keyboard support for the user menu, tabs, stepper, and
  tooltip; acuity still never colour-only (dot + label); `MotionConfig reducedMotion="user"` plus the
  CSS guard means every animation respects the user's setting.

### Bundle (after) vs the 107 KB Phase-0 baseline
- **Entry JS = 139 KB gzip** (the only script in `index.html`; 0 modulepreloads).
- framer-motion feature set = 25 KB gzip (code-split; loaded on mount by `LazyMotion`).
- **three.js isolated in the lazy `Hero3D` chunk = 220 KB gzip** — loads only on `/login` when 3D is
  used; **excluded from the budget**.
- Initial ≈ **164 KB gzip** (entry + motion features), under the ~200 KB budget. CSS 6.6 KB gzip.

### Verification (actual, run once at the end)
- `typecheck` 0 · `lint` 0 · `vitest` **30/30** · `build` OK · `e2e` **1 passed**.
- Full `checkup.sh`: backend `ruff`/`mypy`/`pytest` (**93**) still green (backend untouched) + frontend green.
- Screenshots captured at 1440 & 390, light & dark (`e2e-shots/`), self-reviewed: shell, login (3D),
  dashboard, schedule (now-line), queue, the emergency stepper + mini-timeline, booking modal, tables,
  404 — all cohesive in both themes, no regressions, all contracts intact.

## Phase 5 — Reliability & UX hardening (Groups A/B/C, backend + frontend)

This phase fixed real correctness gaps in the flows and finished wiring the primitives. Unlike the
earlier UI-only phases, **the backend changed** (new migration `0004`, new endpoints, engine
constraint). Every e2e selector/text and the Modal/StatusBadge contracts were preserved.

### Group A — broken flows
- **Escalation lifecycle.** `scheduling_decisions` gains `resolved_at` / `resolved_by` /
  `resolution_note` (migration `0004`). New `POST /scheduling-decisions/{id}/resolve` (triage nurse +
  administrator, note required, writes an audit row). The dashboard now counts and lists **unresolved
  escalations from any day** (previously only today's, and never clearable) and the inbox has a
  **Resolve** action with a note dialog.
- **Acuity is enforced server-side.** Plan/commit are rejected unless the patient has a triage from
  the last 12 h **and** the requested acuity matches it (`triage_required` / `acuity_mismatch`).
  Receptionists see the nurse's recorded acuity read-only (new `GET /patients/{id}/latest-triage`), or
  "A nurse must triage this patient first"; nurses/admins still triage inline.
- **Triage recorded once.** "Review plan" / "Re-plan" no longer re-triage an unchanged
  (patient, acuity, complaint) — tracked by a signature; Re-plan never re-triages.
- **Plan ↔ commit consistency.** The plan response returns its `now`; the client echoes it on commit,
  and a commit whose plan is **>10 min old** is rejected (`plan_expired`).
- **Booking integrity.** Past times are rejected (`past_time`), the slots endpoint hides past slots,
  and a patient can't be booked into two overlapping active appointments (`patient_overlap`). The same
  self-overlap is a **hard engine constraint** (`patient_double_booked`) so emergency placement and
  displaced slots never collide with the patient's own other appointments.

### Group B — UI cleanup
- BookingDialog / PatientForm / DecisionTrace now use the shared **Select / Input / Button / Card**
  primitives (labels, "Confirm booking", and `button[aria-pressed]` slot buttons preserved for e2e).
- The schedule **"now" line is live** (re-renders every ~30 s on today's view).
- **Toast** wired into booking, patient registration, commit success, escalation recorded/resolved,
  and — via a QueryClient `MutationCache` + a small imperative bridge — **all mutation errors**.
  **Skeleton** replaces the spinner for the dashboard, queue, and the three tables. **Tabs** was
  unused and was deleted.
- Each displaced appointment carries its **own duration** into the plan moves (new `duration_min` on
  the engine `Move` + API), so the before/after mini-timeline sizes each block correctly instead of
  reusing the emergency's duration.
- "Schedule another" fully clears the previous patient, complaint, and plan (distinct from "Back",
  which keeps the form for a quick re-plan).
- a11y: `#06101a` on the login hero replaced with a theme-independent **`hero` token**; `aria-label`s
  on the sidebar/drawer `aside` and the nav; collapsed sidebar links get an `aria-label`; CountUp
  exposes the real value to AT (`sr-only`) and hides the animating digits; schedule hover cards work
  on **keyboard and touch** (pointer-type-aware tap toggle) and are linked with `aria-describedby`.

### Group C — housekeeping
- `.gitignore` ignores `*.db` and `e2e-shots/out/`.
- CI's frontend job runs on **pnpm with `--frozen-lockfile`** (lockfile v9 → pnpm 9) instead of npm.

### Trade-offs & simplest-option calls
- **Triage validity** is a 12 h look-back from the plan's `now` (lower bound only) — deterministic
  under tests that drive `now`, and clinically a stale assessment shouldn't authorize scheduling.
- **Engine `patient_busy`** only tracks the patient's appointments on **non-eligible** doctors; those
  on eligible doctors are already in the engine state and handled by the cascade.
- **Migration 0004** adds the `resolved_by` FK only on non-SQLite — SQLite can't `ALTER … ADD
  CONSTRAINT` and doesn't enforce FKs locally; it's the zero-setup dev/test DB, Postgres is prod.
- **Error toasts are global** (one `MutationCache` handler) and additive to the inline messages that
  already sit next to a control — the toast is the ambient, transient channel.
- **"Record escalation"** reuses the existing commit endpoint, which already records an escalated
  decision without touching the schedule — no separate endpoint needed.
- The success toast is deliberately worded ("Walk-in placed") so it never duplicates the step-3
  result card's "Emergency scheduled. 1 appointment rescheduled." text the e2e asserts on.

### Verification (actual output, run after each group)
- Backend — `ruff`: all checks passed · `mypy`: no issues (62 files) · `pytest`: **108 passed**
  (was 93; +15). Migrations `0001→0004` verified up **and** down on fresh SQLite; `seed.py` and
  `e2e_seed.py` both run.
- Frontend — `tsc`: 0 · `eslint`: 0 · `vitest`: **30 passed** (Modal + StatusBadge contracts intact)
  · `build`: OK (entry ~141 KB gzip; three.js stays in the lazy Hero3D chunk) · Playwright signature
  flow: **1 passed**.


