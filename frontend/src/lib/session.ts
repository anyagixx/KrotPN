// FILE: frontend/src/lib/session.ts
// VERSION: 1.0.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Browser-session storage helpers for rollback-compatible JWT auth with a 60-day inactivity limit
//   SCOPE: User auth token persistence, last-seen timestamp tracking, inactivity TTL enforcement, and storage cleanup
//   DEPENDS: M-009 (frontend-user), M-039 (session-security-hardening), localStorage
//   LINKS: M-009, M-039, V-M-039
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   USER_SESSION_IDLE_TIMEOUT_DAYS - Public inactivity TTL policy
//   clearUserSessionStorage - Clears user access/refresh/session timestamp keys
//   touchUserSession - Records current user session activity
//   persistUserSessionTokens - Stores user access/refresh tokens and refreshes activity timestamp
//   hasStoredUserSession - Checks if browser storage currently has an auth token
//   enforceUserSessionTtl - Clears stale stored sessions and returns whether a session remains usable
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added 60-day inactivity TTL helpers for user frontend auth session reuse across browser tabs.
// END_CHANGE_SUMMARY

export const USER_SESSION_IDLE_TIMEOUT_DAYS = 60

const USER_ACCESS_TOKEN_KEY = 'access_token'
const USER_REFRESH_TOKEN_KEY = 'refresh_token'
const USER_SESSION_LAST_SEEN_KEY = 'auth_last_seen_at'
const USER_SESSION_IDLE_TIMEOUT_MS = USER_SESSION_IDLE_TIMEOUT_DAYS * 24 * 60 * 60 * 1000

// START_BLOCK_USER_SESSION_STORAGE
function readLastSeen(): number | null {
  const value = localStorage.getItem(USER_SESSION_LAST_SEEN_KEY)
  if (!value) {
    return null
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function clearUserSessionStorage() {
  localStorage.removeItem(USER_ACCESS_TOKEN_KEY)
  localStorage.removeItem(USER_REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_SESSION_LAST_SEEN_KEY)
}

export function touchUserSession(now = Date.now()) {
  if (hasStoredUserSession()) {
    localStorage.setItem(USER_SESSION_LAST_SEEN_KEY, String(now))
  }
}

export function persistUserSessionTokens(accessToken: string, refreshToken: string, now = Date.now()) {
  localStorage.setItem(USER_ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(USER_REFRESH_TOKEN_KEY, refreshToken)
  localStorage.setItem(USER_SESSION_LAST_SEEN_KEY, String(now))
}

export function hasStoredUserSession() {
  return Boolean(localStorage.getItem(USER_ACCESS_TOKEN_KEY) || localStorage.getItem(USER_REFRESH_TOKEN_KEY))
}

export function enforceUserSessionTtl(now = Date.now()) {
  if (!hasStoredUserSession()) {
    clearUserSessionStorage()
    return false
  }

  const lastSeen = readLastSeen()
  if (lastSeen === null) {
    touchUserSession(now)
    return true
  }

  if (now - lastSeen > USER_SESSION_IDLE_TIMEOUT_MS) {
    clearUserSessionStorage()
    return false
  }

  return true
}
// END_BLOCK_USER_SESSION_STORAGE
