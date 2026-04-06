// FILE: frontend/src/stores/auth.ts
// VERSION: 1.0.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Zustand auth store with persist middleware -- manages user state, authentication status, login/logout
//   SCOPE: User state management, token-based auth status, fetchUser API call, logout cleanup
//   DEPENDS: M-009 (frontend-user), M-002 (users auth)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   useAuthStore - Zustand store with user, isAuthenticated, isLoading, setUser, setLoading, logout, fetchUser
//   BLOCK_AUTH_STORE - Auth store creation (51 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_AUTH_STORE
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User, userApi } from '../lib/api'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean

  setUser: (user: User | null) => void
  setLoading: (loading: boolean) => void
  logout: () => void
  fetchUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: !!localStorage.getItem('access_token'),
      isLoading: false,

      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setLoading: (isLoading) => set({ isLoading }),

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, isAuthenticated: false })
      },

      fetchUser: async () => {
        set({ isLoading: true })
        try {
          const { data } = await userApi.getMe()
          set({ user: data, isAuthenticated: true })
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          set({ user: null, isAuthenticated: false })
        } finally {
          set({ isLoading: false })
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ isAuthenticated: state.isAuthenticated }),
    }
  )
)
// END_BLOCK_AUTH_STORE
