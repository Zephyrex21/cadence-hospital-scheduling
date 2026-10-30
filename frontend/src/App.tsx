import { Route, Routes } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { BackendWakeBanner } from './components/BackendWakeBanner'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AuditPage } from './routes/AuditPage'
import { DashboardPage } from './routes/DashboardPage'
import { DisplacementsPage } from './routes/DisplacementsPage'
import { EmergencyPage } from './routes/EmergencyPage'
import { LoginPage } from './routes/LoginPage'
import { NotFoundPage } from './routes/NotFoundPage'
import { PatientsPage } from './routes/PatientsPage'
import { QueuePage } from './routes/QueuePage'
import { SchedulePage } from './routes/SchedulePage'

export function App() {
  return (
    <>
      <BackendWakeBanner />
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
                  <Route path="/schedule" element={<SchedulePage />} />
                  <Route path="/queue" element={<QueuePage />} />
                  <Route path="/emergency" element={<EmergencyPage />} />
                  <Route path="/displacements" element={<DisplacementsPage />} />
                  <Route path="/audit" element={<AuditPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </AppShell>
            </ProtectedRoute>
          }
        />
      </Routes>
    </>
  )
}
