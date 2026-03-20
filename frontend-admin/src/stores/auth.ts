import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AdminUser {
  id: number
  email: string
  role: string
  is_superuser: boolean
}

interface AuthState {
  user: AdminUser | null
  token: string | null
  isAuthenticated: boolean
  isAdmin: boolean
  setUser: (user: AdminUser | null) => void
  setToken: (token: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: localStorage.getItem('admin_token'),
      isAuthenticated: !!localStorage.getItem('admin_token'),
      isAdmin: false,
      
      setUser: (user) => set({ 
        user, 
        isAuthenticated: !!user,
        isAdmin: user?.role === 'admin' || user?.role === 'superadmin'
      }),
      
      setToken: (token) => {
        if (token) localStorage.setItem('admin_token', token)
        else localStorage.removeItem('admin_token')
        set({ token, isAuthenticated: !!token })
      },
      
      logout: () => {
        localStorage.removeItem('admin_token')
        set({ user: null, token: null, isAuthenticated: false, isAdmin: false })
      },
    }),
    { name: 'admin-auth' }
  )
)
