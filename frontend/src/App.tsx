import { type ComponentType, lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { BackendWakeBanner } from './components/BackendWakeBanner'
import { ProtectedRoute } from './components/ProtectedRoute'
import { NotFoundPage } from './routes/NotFoundPage'

// Each screen is its own chunk, so the first paint (login / dashboard) doesn't download the
// schedule, emergency and audit screens it may never open.
const lazyRoute = <K extends string>(
  load: () => Promise<Record<K, ComponentType>>,
  name: K,
) => lazy(async () => ({ default: (await load())[name] }))

const AuditPage = lazyRoute(() => import('./routes/AuditPage'), 'AuditPage')
const DashboardPage = lazyRoute(() => import('./routes/DashboardPage'), 'DashboardPage')
const DisplacementsPage = lazyRoute(() => import('./routes/DisplacementsPage'), 'DisplacementsPage')
const EmergencyPage = lazyRoute(() => import('./routes/EmergencyPage'), 'EmergencyPage')
const LoginPage = lazyRoute(() => import('./routes/LoginPage'), 'LoginPage')
const NotificationsPage = lazyRoute(
  () => import('./routes/NotificationsPage'),
  'NotificationsPage',
)
const PatientsPage = lazyRoute(() => import('./routes/PatientsPage'), 'PatientsPage')
const QueuePage = lazyRoute(() => import('./routes/QueuePage'), 'QueuePage')
const SchedulePage = lazyRoute(() => import('./routes/SchedulePage'), 'SchedulePage')
const StaffPage = lazyRoute(() => import('./routes/StaffPage'), 'StaffPage')

function PageLoading() {
  return (
    <div role="status" aria-busy aria-label="Loading" className="p-8 text-sm text-muted">
      Loading…
    </div>
  )
}

export function App() {
  return (
    <>
      <BackendWakeBanner />
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/patients" element={<PatientsPage />} />
                    <Route path="/staff" element={<StaffPage />} />
                    <Route path="/schedule" element={<SchedulePage />} />
                    <Route path="/queue" element={<QueuePage />} />
                    <Route path="/emergency" element={<EmergencyPage />} />
                    <Route path="/displacements" element={<DisplacementsPage />} />
                    <Route path="/notifications" element={<NotificationsPage />} />
                      <Route path="/audit" element={<AuditPage />} />
                    <Route path="*" element={<NotFoundPage />} />
                  </Routes>
                </AppShell>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Suspense>
    </>
  )
}
