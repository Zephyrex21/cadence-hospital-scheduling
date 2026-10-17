import { m } from 'framer-motion'
import {
  CalendarClock,
  CalendarRange,
  ChevronDown,
  ChevronLeft,
  Clock,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  ScrollText,
  Siren,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

import { useAuth } from '../features/auth/AuthContext'
import { EMERGENCY_ROLES, ROLE_LABELS } from '../features/auth/roles'
import { ThemeToggle } from '../theme/ThemeToggle'
import type { Role, User } from '../types'
import { Tooltip } from './Tooltip'

interface NavEntry {
  to: string
  label: string
  icon: ReactNode
  roles?: readonly Role[]
}

const ADMIN_ONLY: readonly Role[] = ['administrator']
const SIDEBAR_KEY = 'cadence.sidebar'

const NAV: NavEntry[] = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
  { to: '/schedule', label: 'Schedule', icon: <CalendarRange size={18} /> },
  { to: '/queue', label: 'Queue', icon: <ListChecks size={18} /> },
  { to: '/emergency', label: 'Emergency', icon: <Siren size={18} />, roles: EMERGENCY_ROLES },
  { to: '/displacements', label: 'Displacements', icon: <CalendarClock size={18} /> },
  { to: '/patients', label: 'Patients', icon: <Users size={18} /> },
  { to: '/audit', label: 'Decisions & audit', icon: <ScrollText size={18} />, roles: ADMIN_ONLY },
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
    <div className="flex min-h-screen bg-canvas">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[80] focus:rounded-control focus:bg-brand focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-surface"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        aria-label="Sidebar"
        className={`hidden shrink-0 flex-col border-r border-hairline bg-surface/80 backdrop-blur-md transition-[width] duration-250 ease-out-soft lg:flex ${
          collapsed ? 'w-[76px]' : 'w-64'
        }`}
      >
        <Brand collapsed={collapsed} />
        <NavLinks items={visible} collapsed={collapsed} layoutId="nav-indicator" />
        <div className="border-t border-hairline p-3">
          <button
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex w-full items-center justify-center gap-2 rounded-control px-3 py-2 text-sm text-muted transition-colors hover:bg-canvas hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
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
            className="absolute inset-0 bg-scrim/50 backdrop-blur-sm animate-fade-in"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-hairline bg-surface shadow-lg animate-slide-in-left" aria-label="Menu">
            <div className="flex items-center justify-between pr-2">
              <Brand collapsed={false} />
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="rounded-control p-2 text-muted transition-colors hover:bg-canvas hover:text-ink"
              >
                <X size={18} />
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
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-hairline bg-surface/80 px-4 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              aria-expanded={mobileOpen}
              className="rounded-control p-2 text-slate transition-colors hover:bg-canvas lg:hidden"
            >
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-2 lg:hidden">
              <div className="flex h-7 w-7 items-center justify-center rounded-card bg-brand-gradient text-white">
                <span className="font-display text-sm font-semibold">C</span>
              </div>
              <span className="font-display text-sm font-semibold text-ink">Cadence</span>
            </div>
            <ClinicClock />
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <SyntheticPill />
            <ThemeToggle />
            {user ? <UserMenu user={user} logout={logout} /> : null}
          </div>
        </header>

        <main
          id="main-content"
          className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8"
        >
          <div key={location.pathname} className="animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <div className="flex items-center gap-3 px-5 py-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-card bg-brand-gradient text-white shadow-xs">
        <span className="font-display text-lg font-semibold">C</span>
      </div>
      {!collapsed && (
        <div className="min-w-0">
          <p className="truncate font-display text-base font-semibold text-ink">Cadence</p>
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
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          onClick={onNavigate}
          title={collapsed ? item.label : undefined}
          aria-label={collapsed ? item.label : undefined}
          className={({ isActive }) =>
            `relative flex items-center gap-3 rounded-control px-3 py-2 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-brand/50 ${
              isActive ? 'text-brand' : 'text-slate hover:bg-canvas hover:text-ink'
            } ${collapsed ? 'justify-center' : ''}`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <m.span
                  layoutId={layoutId}
                  className="absolute inset-0 rounded-control bg-brand/10 ring-1 ring-inset ring-brand/20"
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                />
              )}
              <span className="relative z-10 flex h-5 w-5 shrink-0 items-center justify-center">
                {item.icon}
              </span>
              {!collapsed && <span className="relative z-10 truncate">{item.label}</span>}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

function ClinicClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  const time = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'UTC',
  }).format(now)
  return (
    <div className="hidden items-center gap-2 text-sm text-slate sm:flex">
      <Clock size={15} className="text-muted" aria-hidden />
      <span className="tabular-nums">{time}</span>
      <span className="text-xs text-muted">UTC</span>
    </div>
  )
}

function SyntheticPill() {
  return (
    <Tooltip label="Synthetic demo data only — not for clinical use. Cadence is a scheduling tool, not a diagnostic system.">
      <span
        tabIndex={0}
        role="note"
        className="hidden cursor-default items-center gap-1.5 rounded-pill bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning ring-1 ring-inset ring-warning/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 sm:inline-flex"
      >
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-warning" />
        Synthetic data
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
        className="flex items-center gap-2 rounded-pill py-1 pl-1 pr-2 text-sm transition-colors hover:bg-canvas focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-pill bg-brand text-xs font-semibold text-surface">
          {initials}
        </span>
        <span className="hidden max-w-[8rem] truncate font-medium text-ink sm:block">
          {user.name}
        </span>
        <ChevronDown size={14} className="text-muted" aria-hidden />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-card border border-hairline bg-elevated shadow-lg animate-scale-in"
        >
          <div className="border-b border-hairline px-4 py-3">
            <p className="truncate text-sm font-medium text-ink">{user.name}</p>
            <p className="text-xs text-muted">{ROLE_LABELS[user.role]}</p>
          </div>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false)
              logout()
            }}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-slate transition-colors hover:bg-canvas"
          >
            <LogOut size={15} aria-hidden />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
