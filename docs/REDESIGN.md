# Redesign: "Cream & Moon" + Indian clinic localisation

## Design system
- **Single source of truth:** `frontend/src/styles/tokens.css` (CSS variables, RGB channels) mapped
  by `tailwind.config.ts`. Components use semantic tokens only — no hardcoded colours.
- **Light (cream):** canvas `#F6F2E9`, cards `#FFFDF9`, ink `#1D1D1F`, warm hairlines and shadows.
  **Dark (moon black):** true-black canvas, `#121214` surfaces, `#F5F5F7` text, faint blue moonglow.
- **Accent:** Apple blue (`#0071E3` fill / `#0066CC` text in light, `#0A84FF` in dark). Acuity
  A1–A5 stay colour + label + shape, never colour alone.
- **Depth & shine:** layered warm shadows, a 1px top highlight on cards (`--hl`), a lit "shine"
  gradient on primary buttons (`.btn-shine`), frosted glass (`.glass`) on the sidebar, top bar,
  menus and toasts, large radii (12 / 20 / 28 px).
- **Type:** SF Pro on Apple devices, bundled Inter Variable elsewhere; tight display tracking,
  tabular numerals for times and counts.
- **Icons:** Phosphor (`@phosphor-icons/react`) via one module, `components/icons.tsx` — regular
  weight in dense UI, duotone/fill for navigation and emphasis. Custom `BrandMark` logo.
- **Login hero:** pure CSS/SVG (`HeroScene`) replaces the three.js scene — about 800 kB of JS removed.
- **Accessibility:** `styles/contrast.test.ts` fails the build if any text/background token pair
  drops below WCAG AA (4.5:1) in either theme.

## Indian localisation
- `frontend/src/lib/time.ts` is the only place time is formatted: IST, 12-hour clock
  ("4:42 pm"), day-first dates ("30 Oct 2026"), en-IN number grouping, clinic-day maths.
- Backend `clinic_day_bounds()` makes "today" the IST day (starts 18:30 UTC the evening before).
- Seed data: Indian staff, doctors (General Medicine, Cardiology), ten patients with +91 mobiles,
  cities, blood groups, emergency contacts and notes; shifts defined as IST OPD sessions
  (9:00 am–1:00 pm, 2:00–6:00 pm) for the next 14 days.
- Patients: richer record (city, blood group, emergency contact, notes), search by name / MRN /
  phone / city, a details view, and a registration form that accepts any text (incl. Devanagari).
