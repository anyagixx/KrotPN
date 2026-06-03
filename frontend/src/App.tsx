// FILE: frontend/src/App.tsx
// VERSION: 1.0.0
// ROLE: ENTRY_POINT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Root application component with public landing, routing setup, auth guard, and toaster configuration
//   SCOPE: BrowserRouter, route definitions (public landing, login, register, verify-email, password recovery, protected dashboard layout + child routes), legacy route redirects, PrivateRoute HOC, Toaster config, Matrix visual shell mount
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), M-073 (premium-public-site)
//   LINKS: M-009 (frontend-user), M-073
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PrivateRoute - Auth guard component redirecting to /login when not authenticated
//   App - Root component with routes, toaster setup, and Phase-52 visual shell
//   BLOCK_PRIVATE_ROUTE - PrivateRoute auth guard (~10 lines)
//   BLOCK_APP - App component with routing (72 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.1.0 - Added Phase-56 public landing route and moved authenticated cabinet routes under /dashboard with legacy redirects
//   LAST_CHANGE: v3.0.0 - Mounted Phase-52 Matrix VisualShell around the user route tree
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 forgot/reset password routes
//   LAST_CHANGE: 2026-05-13 - Added Phase-28 verify-email route for pending registration activation
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_PRIVATE_ROUTE
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from './stores/auth'
import Layout from './components/Layout'
import VisualShell from './components/VisualShell'
import Login from './pages/Login'
import Register from './pages/Register'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import VerifyEmail from './pages/VerifyEmail'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import Config from './pages/Config'
import Subscription from './pages/Subscription'
import Referrals from './pages/Referrals'
import Settings from './pages/Settings'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
// END_BLOCK_PRIVATE_ROUTE

// START_BLOCK_APP
function App() {
  const { isAuthenticated, user, fetchUser } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated && !user) {
      void fetchUser()
    }
  }, [fetchUser, isAuthenticated, user])

  return (
    <BrowserRouter>
      <VisualShell>
        <div className="min-h-screen">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route
              path="/dashboard"
              element={
                <PrivateRoute>
                  <Layout />
                </PrivateRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="config" element={<Config />} />
              <Route path="subscription" element={<Subscription />} />
              <Route path="referrals" element={<Referrals />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="/config" element={<Navigate to="/dashboard/config" replace />} />
            <Route path="/subscription" element={<Navigate to="/dashboard/subscription" replace />} />
            <Route path="/referrals" element={<Navigate to="/dashboard/referrals" replace />} />
            <Route path="/settings" element={<Navigate to="/dashboard/settings" replace />} />
          </Routes>
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#10242d',
                color: '#eff8fb',
                border: '1px solid rgba(157, 203, 216, 0.14)',
                borderRadius: '18px',
                boxShadow: '0 22px 60px rgba(2, 10, 14, 0.3)',
              },
            }}
          />
        </div>
      </VisualShell>
    </BrowserRouter>
  )
}

export default App
// END_BLOCK_APP
