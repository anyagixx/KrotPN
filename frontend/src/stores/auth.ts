// FILE: frontend/src/stores/auth.ts
// VERSION: 1.1.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Zustand auth store with persist middleware -- manages user state, authentication status, login/logout, and 60-day inactivity TTL
//   SCOPE: User state management, token-based auth status, fetchUser API call, session TTL enforcement, logout cleanup
//   DEPENDS: M-009 (frontend-user), M-002 (users auth), M-039 (session-security-hardening)
//   LINKS: M-009 (frontend-user), M-039
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   useAuthStore - Zustand store with user, isAuthenticated, isLoading, setUser, setLoading, logout, fetchUser
//   session helpers - Enforce 60-day inactivity TTL before session reuse
//   BLOCK_AUTH_STORE - Auth store creation (51 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Added 60-day inactivity TTL enforcement and last-seen refresh for stored browser sessions.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_AUTH_STORE
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User, userApi } from '../lib/api'
import { clearUserSessionStorage, enforceUserSessionTtl, touchUserSession } from '../lib/session'

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
      isAuthenticated: enforceUserSessionTtl(),
      isLoading: false,

      setUser: (user) => {
        if (user) {
          touchUserSession()
        }
        set({ user, isAuthenticated: !!user })
      },
      setLoading: (isLoading) => set({ isLoading }),

      logout: () => {
        clearUserSessionStorage()
        set({ user: null, isAuthenticated: false })
      },

      fetchUser: async () => {
        if (!enforceUserSessionTtl()) {
          set({ user: null, isAuthenticated: false, isLoading: false })
          return
        }

        set({ isLoading: true })
        try {
          const { data } = await userApi.getMe()
          touchUserSession()
          set({ user: data, isAuthenticated: true })
        } catch {
          clearUserSessionStorage()
          set({ user: null, isAuthenticated: false })
        } finally {
          set({ isLoading: false })
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ isAuthenticated: state.isAuthenticated }),
      merge: (persistedState, currentState) => ({
        ...currentState,
        ...(persistedState as Partial<AuthState>),
        user: null,
        isAuthenticated: enforceUserSessionTtl(),
      }),
    }
  )
)
// END_BLOCK_AUTH_STORE
