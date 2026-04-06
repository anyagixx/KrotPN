// FILE: frontend-admin/src/stores/auth.ts
// VERSION: 1.0.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Authentication state management for admin panel
//   SCOPE: AdminUser profile, JWT token, login/logout lifecycle
//   DEPENDS: M-010 (frontend-admin), zustand (persist middleware), localStorage
//   LINKS: M-010 (frontend-admin)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AdminUser - Admin user profile interface
//   AuthState - Auth store state interface (user, token, isAuthenticated, isAdmin)
//   useAuthStore - Zustand auth store with login, logout, persist middleware
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format with START/END blocks
// END_CHANGE_SUMMARY
//
//   LINKS: M-010
// MODULE_MAP:
//   useAuthStore — exported Zustand store (user, token, auth actions)
// CHANGE_SUMMARY: v2.8.0 — initial GRACE annotation
// =============================================================================
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// START_BLOCK: AdminUser interface
interface AdminUser {
  id: number
  email: string
  role: string
  is_superuser: boolean
}
// END_BLOCK: AdminUser interface

// START_BLOCK: AuthState interface
interface AuthState {
  user: AdminUser | null
  token: string | null
  isAuthenticated: boolean
  isAdmin: boolean
  setUser: (user: AdminUser | null) => void
  setToken: (token: string | null) => void
  logout: () => void
}
// END_BLOCK: AuthState interface

// START_BLOCK: useAuthStore
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
// END_BLOCK: useAuthStore
