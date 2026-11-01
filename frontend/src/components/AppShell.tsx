import { m } from 'framer-motion'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

import { useAuth } from '../features/auth/AuthContext'
import { EMERGENCY_ROLES, ROLE_LABELS } from '../features/auth/roles'
import { CLINIC_TZ_LABEL, formatDateShort, formatTime } from '../lib/time'
import { ThemeToggle } from '../theme/ThemeToggle'
import type { Role, User } from '../types'
import { BrandMark } from './BrandMark'
import {
  CalendarBlank,
  ChevronDown,
  ChevronLeft,
  ClipboardText,
  Clock,
  ClockCounterClockwise,
  List,
  ListChecks,
  LogOut,
  Siren,
  SquaresFour,
  UsersThree,
  X,
  type Icon,
} from './icons'
import { Tooltip } from './Tooltip'

interface NavEntry {
  to: string
  label: string
  icon: Icon
  roles?: readonly Role[]
}

const ADMIN_ONLY: readonly Role[] = ['administrator']
const SIDEBAR_KEY = 'cadence.sidebar'

const NAV: NavEntry[] = [
  { to: '/', label: 'Dashboard', icon: SquaresFour },
  { to: '/schedule', label: 'Schedule', icon: CalendarBlank },
  { to: '/queue', label: 'Queue', icon: ListChecks },
  { to: '/emergency', label: 'Emergency', icon: Siren, roles: EMERGENCY_ROLES },
  { to: '/displacements', label: 'Displacements', icon: ClockCounterClockwise },
  { to: '/patients', label: 'Patients', icon: UsersThree },
  { to: '/audit', label: 'Decisions & audit', icon: ClipboardText, roles: ADMIN_ONLY },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(
    () => typeof localStorage !== 'undefined' && localStorage.getItem(SIDEBAR_KEY) === 'collapsed',
  )
  const visible = NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role)))

  useEffect(() => setMobileOpen(false), [location.pathname])
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMobileOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [mobileOpen])

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? 'collapsed' : 'expanded')
      } catch {
        /* ignore */
      }
      return next
    })
  }

  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[80] focus:rounded-pill focus:bg-brand-fill focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-on-brand"
      >
        Skip to content
      </a>

      {/* Desktop sidebar — a floating frosted panel */}
      <aside
        aria-label="Sidebar"
        className={`glass sticky top-3 m-3 mr-0 hidden h-[calc(100vh-1.5rem)] shrink-0 flex-col rounded-modal border border-hairline shadow-card transition-[width] duration-300 ease-out-soft lg:flex ${
          collapsed ? 'w-[84px]' : 'w-[264px]'
        }`}
      >
        <Brand collapsed={collapsed} />
        <NavLinks items={visible} collapsed={collapsed} layoutId="nav-indicator" />
        <div className="p-3">
          <button
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex w-full items-center justify-center gap-2 rounded-control px-3 py-2 text-[13px] text-muted transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
          >
            <ChevronLeft size={16} className={collapsed ? 'rotate-180' : ''} aria-hidden />
            {!collapsed && 'Collapse'}
          </button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-scrim/40 backdrop-blur-md animate-fade-in"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside
            className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-hairline bg-surface shadow-lg animate-slide-in-left"
            aria-label="Menu"
          >
            <div className="flex items-center justify-between pr-3">
              <Brand collapsed={false} />
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="rounded-pill bg-ink/5 p-2 text-muted transition-colors hover:bg-ink/10 hover:text-ink"
              >
                <X size={16} weight="bold" />
              </button>
            </div>
            <NavLinks
              items={visible}
              collapsed={false}
              layoutId="nav-indicator-mobile"
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-hairline px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              aria-expanded={mobileOpen}
              className="rounded-pill bg-ink/5 p-2 text-slate transition-colors hover:bg-ink/10 lg:hidden"
            >
              <List size={20} />
            </button>
            <div className="flex items-center gap-2 lg:hidden">
              <BrandMark size={28} />
              <span className="font-display text-sm font-semibold text-ink">Cadence</span>
            </div>
            <ClinicClock />
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <DemoPill />
            <ThemeToggle />
            {user ? <UserMenu user={user} logout={logout} /> : null}
          </div>
        </header>

        <main
          id="main-content"
          className="mx-auto w-full max-w-[1180px] flex-1 px-4 py-7 sm:px-6 lg:px-8 lg:py-9"
        >
          <div key={location.pathname} className="animate-fade-in-up">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <div className={`flex items-center gap-3 px-5 pb-3 pt-5 ${collapsed ? 'justify-center px-0' : ''}`}>
      <BrandMark size={38} />
      {!collapsed && (
        <div className="min-w-0">
          <p className="truncate font-display text-[17px] font-semibold leading-tight text-ink">
            Cadence
          </p>
          <p className="truncate text-xs text-muted">Clinical flow</p>
        </div>
      )}
    </div>
  )
}

function NavLinks({
  items,
  collapsed,
  layoutId,
  onNavigate,
}: {
  items: NavEntry[]
  collapsed: boolean
  layoutId: string
  onNavigate?: () => void
}) {
  return (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3">
      {items.map((item) => {
        const NavIcon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            aria-label={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              `relative flex items-center gap-3 rounded-control px-3 py-2.5 text-[14px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-brand/50 ${
                isActive ? 'text-brand' : 'text-slate hover:bg-ink/5 hover:text-ink'
              } ${collapsed ? 'justify-center' : ''}`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <m.span
                    layoutId={layoutId}
                    className="absolute inset-0 rounded-control bg-brand/10"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
                <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center">
                  <NavIcon size={22} weight={isActive ? 'duotone' : 'regular'} aria-hidden />
                </span>
                {!collapsed && <span className="relative z-10 truncate">{item.label}</span>}
              </>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

/** Live clinic clock in Indian Standard Time: "Fri, 30 Oct · 4:42 pm IST". */
function ClinicClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15_000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="hidden items-center gap-2 text-sm text-slate sm:flex" aria-label="Clinic time">
      <Clock size={16} weight="duotone" className="text-muted" aria-hidden />
      <span className="text-muted">{formatDateShort(now)}</span>
      <span className="font-medium tabular-nums text-ink">{formatTime(now)}</span>
      <span className="rounded-pill bg-ink/[0.06] px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-muted">
        {CLINIC_TZ_LABEL}
      </span>
    </div>
  )
}

function DemoPill() {
  return (
    <Tooltip label="Demo environment — scheduling tool for demonstration, not a diagnostic or clinical-decision system.">
      <span
        tabIndex={0}
        role="note"
        className="hidden cursor-default items-center gap-1.5 rounded-pill bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 sm:inline-flex"
      >
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-warning" />
        Demo
      </span>
    </Tooltip>
  )
}

function UserMenu({ user, logout }: { user: User; logout: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const initials = user.name
    .replace(/^Dr\.?\s+/i, '')
    .split(' ')
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-pill py-1 pl-1 pr-2.5 text-sm transition-colors hover:bg-ink/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-pill bg-brand-gradient text-xs font-semibold text-on-brand shadow-xs">
          {initials}
        </span>
        <span className="hidden max-w-[9rem] truncate font-medium text-ink sm:block">
          {user.name}
        </span>
        <ChevronDown size={14} className="text-muted" aria-hidden />
      </button>
      {open && (
        <div
          role="menu"
          className="glass absolute right-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-card border border-hairline shadow-lg animate-scale-in"
        >
          <div className="border-b border-hairline px-4 py-3">
            <p className="truncate text-sm font-semibold text-ink">{user.name}</p>
            <p className="text-xs text-muted">{ROLE_LABELS[user.role]}</p>
          </div>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false)
              logout()
            }}
            className="flex w-full items-center gap-2.5 px-4 py-3 text-sm text-slate transition-colors hover:bg-ink/5 hover:text-ink"
          >
            <LogOut size={18} aria-hidden />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
