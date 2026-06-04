// FILE: frontend-admin/src/main.tsx
// VERSION: 1.1.0
// ROLE: ENTRY_POINT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Application entry point — mounts React router, query client, auth-guarded routes, and Phase-74-safe retired admin route redirects
//   SCOPE: BrowserRouter, QueryClientProvider, PrivateRoute, page route definitions including MTProto admin ops, retired /plans redirect, Matrix visual shell mount
//   DEPENDS: M-010 (frontend-admin), M-047 (mtproto-admin-ops), M-068 (tariff-catalog), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), react-router-dom, @tanstack/react-query, stores/auth
//   LINKS: M-010 (frontend-admin), M-047, M-068, M-070, M-071, Phase-74
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   queryClient - TanStack Query client instance
//   PrivateRoute - Auth guard component redirecting to /login
//   App mount - ReactDOM.createRoot with React.StrictMode, Phase-52 visual shell, and Phase-74 /plans redirect
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.4.0 - Phase-74 retired the visible admin /plans page by redirecting direct visits back to the dashboard.
//   LAST_CHANGE: v3.3.0 - Mounted Phase-52 Matrix VisualShell around the admin route tree
//   LAST_CHANGE: v3.2.0 - Added Phase-33 /mtproto admin route
//   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format with START/END blocks
// END_CHANGE_SUMMARY
//
//   LINKS: M-010
// MODULE_MAP:
//   queryClient — shared React Query client
//   PrivateRoute — auth gate component (redirects /login if !isAuthenticated || !isAdmin)
//   Routes — /login (public), / (private Layout + nested pages)
// CHANGE_SUMMARY: v2.8.0 — initial GRACE annotation
// =============================================================================
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from 'react-query'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Users from './pages/Users'
import Devices from './pages/Devices'
import MTProto from './pages/MTProto'
import Servers from './pages/Servers'
import Analytics from './pages/Analytics'
import Layout from './components/Layout'
import VisualShell from './components/VisualShell'
import { useAuthStore } from './stores/auth'
import './index.css'

// START_BLOCK: QueryClient
const queryClient = new QueryClient()
// END_BLOCK: QueryClient

// START_BLOCK: PrivateRoute
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAdmin } = useAuthStore()
  if (!isAuthenticated || !isAdmin) return <Navigate to="/login" />
  return <>{children}</>
}
// END_BLOCK: PrivateRoute

// START_BLOCK: App mount
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <VisualShell>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
              <Route index element={<Dashboard />} />
              <Route path="users" element={<Users />} />
              <Route path="devices" element={<Devices />} />
              <Route path="mtproto" element={<MTProto />} />
              <Route path="servers" element={<Servers />} />
              <Route path="plans" element={<Navigate to="/" replace />} />
              <Route path="analytics" element={<Analytics />} />
            </Route>
          </Routes>
        </VisualShell>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
// END_BLOCK: App mount
