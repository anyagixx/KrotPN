import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from './stores/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
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

function App() {
  const { isAuthenticated, user, fetchUser } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated && !user) {
      void fetchUser()
    }
  }, [fetchUser, isAuthenticated, user])

  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/"
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
    </BrowserRouter>
  )
}

export default App
