// FILE: frontend/src/lib/api.ts
// VERSION: 1.1.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Axios API client with auth interceptors, token refresh logic, and typed API service modules
//   SCOPE: HTTP client setup, request/response interceptors, 60-day inactivity TTL enforcement, auto token refresh, API namespaces (auth, user, vpn, device, billing, referral, mtproto)
//   DEPENDS: M-002 (users auth), M-003 (vpn), M-004 (billing), M-005 (referrals), M-039 (session-security-hardening), M-045 (mtproto-user-cabinet)
//   LINKS: M-009 (frontend-user), M-039, M-045
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   api - Axios instance with interceptors
//   User, TokenResponse, PendingRegistrationResponse, VPNConfig, UserDevice, DeviceList, DeviceConfigBundle - Types
//   VPNStats, VPNNodeStatus, VPNRouteStatus, UserStats - Types
//   Plan, SubscriptionStatus, ReferralStats, ReferralListItem, MTProtoProxyResponse - Types
//   authApi - Login, register, verify email, password reset, telegram auth, refresh
//   userApi - Get me, stats, update profile, change password
//   vpnApi - Config, download, QR, stats, nodes, routes
//   CONFIG_DOWNLOAD_MIME_TYPE - Browser-safe MIME type for .conf attachment downloads
//   session helpers - Enforce user session inactivity TTL and persist refreshed tokens
//   deviceApi - List, create, read selected config, download selected config, QR, rotate, revoke
//   billingApi - Get plans, subscription, create payment
//   referralApi - Get code, stats, list
//   mtprotoApi - Get current user's owner-only Telegram proxy state
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: 2026-06-04 - Added Phase-71 per-device config, download, and QR API methods.
//   LAST_CHANGE: 2026-06-04 - Added Phase-69 referral masked identity and subscription access_label API fields.
//   LAST_CHANGE: 2026-06-04 - Added 60-day user session inactivity TTL enforcement and last-seen refresh through API requests.
//   LAST_CHANGE: 2026-06-02 - Added Phase-50 paid tariff catalog fields to billing plan API contract
//   LAST_CHANGE: 2026-06-01 - Added Phase-48 octet-stream MIME contract for VPN config downloads
//   LAST_CHANGE: 2026-06-01 - Added Phase-45 subscription countdown and pending trial API fields
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 password reset auth API contracts
//   LAST_CHANGE: 2026-05-14 - Added Phase-31 MTProto owner proxy API contract
//   LAST_CHANGE: 2026-05-13 - Added Phase-28 pending registration and verify-email auth API contracts
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_API_CLIENT
import axios from 'axios'
import { clearUserSessionStorage, enforceUserSessionTtl, persistUserSessionTokens, touchUserSession } from './session'

const API_BASE = '/api/v1'
export const CONFIG_DOWNLOAD_MIME_TYPE = 'application/octet-stream'

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})
// END_BLOCK_API_CLIENT

// START_BLOCK_REQUEST_INTERCEPTOR
// Request interceptor - add auth token
api.interceptors.request.use((config) => {
  if (!enforceUserSessionTtl()) {
    return config
  }

  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
    touchUserSession()
  }
  return config
})
// END_BLOCK_REQUEST_INTERCEPTOR

// START_BLOCK_RESPONSE_INTERCEPTOR
// Response interceptor - handle auth errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      // Try to refresh token
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const refreshApi = axios.create({ baseURL: API_BASE })
          const { data } = await refreshApi.post('/auth/refresh', {
            refresh_token: refreshToken,
          })

          persistUserSessionTokens(data.access_token, data.refresh_token)

          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
          return api(originalRequest)
        } catch {
          // Refresh failed, clear tokens
          clearUserSessionStorage()
          window.location.href = '/login'
        }
      } else {
        clearUserSessionStorage()
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)
// END_BLOCK_RESPONSE_INTERCEPTOR

// Types
export interface User {
  id: number
  email: string | null
  telegram_id: number | null
  telegram_username: string | null
  name: string | null
  display_name: string
  language: string
  role: string
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface PendingRegistrationResponse {
  email: string
  status: string
  expires_at: string
  delivery_status: string
  message: string
}

export interface PasswordResetResponse {
  status: string
  message: string
}

export interface VPNConfig {
  config: string
  server_name: string
  server_location: string
  route_name?: string | null
  entry_server_name?: string | null
  entry_server_location?: string | null
  exit_server_name?: string | null
  exit_server_location?: string | null
  address: string
  created_at: string
}

export interface UserDevice {
  id: number
  device_key: string
  name: string
  platform?: string | null
  status: string
  config_version: number
  created_at: string
  updated_at: string
  revoked_at?: string | null
  blocked_at?: string | null
  last_seen_at?: string | null
  last_handshake_at?: string | null
  last_endpoint?: string | null
  block_reason?: string | null
}

export interface DeviceList {
  devices: UserDevice[]
  consumed_slots: number
  device_limit: number
}

export interface DeviceConfigBundle extends VPNConfig {
  device: UserDevice
}

export interface VPNStats {
  total_upload_bytes: number
  total_download_bytes: number
  total_upload_formatted: string
  total_download_formatted: string
  last_handshake_at: string | null
  is_connected: boolean
  server_name: string
  server_location: string
}

export interface VPNNodeStatus {
  id: number
  name: string
  role: string
  country_code: string
  location: string
  endpoint: string
  port: number
  public_key: string
  is_active: boolean
  is_online: boolean
  is_entry_node: boolean
  is_exit_node: boolean
  current_clients: number
  max_clients: number
  load_percent: number
}

export interface VPNRouteStatus {
  id: number
  name: string
  entry_node_id: number
  entry_node_name: string
  entry_node_location: string
  exit_node_id?: number | null
  exit_node_name?: string | null
  exit_node_location?: string | null
  is_active: boolean
  is_default: boolean
  tunnel_interface?: string | null
  tunnel_status: string
  priority: number
  current_clients: number
  max_clients: number
  load_percent: number
}

export interface UserStats {
  total_upload_bytes: number
  total_download_bytes: number
  subscription_days_left: number
  has_active_subscription: boolean
  referrals_count: number
  referral_bonus_days: number
}

export interface Plan {
  id: number
  slug: string | null
  name: string
  description: string | null
  price: number
  currency: string
  duration_days: number
  device_limit: number
  features: string[]
  is_active: boolean
  is_canonical: boolean
  is_popular: boolean
  sort_order: number
}

export interface SubscriptionStatus {
  has_subscription: boolean
  is_active: boolean
  is_trial: boolean
  pending_activation: boolean
  pending_duration_days: number | null
  plan_name: string | null
  days_left: number
  expires_at: string | null
  activated_at: string | null
  started_at: string | null
  remaining_seconds: number
  remaining_days: number
  remaining_hours: number
  remaining_minutes: number
  active_from: string | null
  active_until: string | null
  access_label: string | null
  is_recurring: boolean
}

export interface ReferralStats {
  total_referrals: number
  bonus_days_earned: number
  paid_referrals?: number
}

export interface ReferralListItem {
  id: number
  referred_identity: string
  referred_email_masked?: string
  bonus_given: boolean
  bonus_days: number
  created_at: string
  first_payment_at: string | null
}

export type MTProtoProxyStatus = 'activated' | 'pending' | 'degraded' | 'unverified' | 'reissue_required'

export interface MTProtoProxyResponse {
  status: MTProtoProxyStatus
  safe_message: string
  action_required: string | null
  assignment_id: number | null
  server: string | null
  port: number | null
  secret: string | null
  tg_link: string | null
  sni: string | null
  credential_mode: string | null
  rotation_marker: string | null
  reissue_required: boolean
}

// START_BLOCK_AUTH_API
// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),

  register: (email: string, password: string, referral_code?: string) =>
    api.post<PendingRegistrationResponse>('/auth/register', { email, password, referral_code }),

  verifyEmail: (token: string) =>
    api.post<TokenResponse>('/auth/verify-email', { token }),

  requestPasswordReset: (email: string) =>
    api.post<PasswordResetResponse>('/auth/password-reset/request', { email }),

  confirmPasswordReset: (token: string, new_password: string) =>
    api.post<PasswordResetResponse>('/auth/password-reset/confirm', { token, new_password }),

  telegramAuth: (telegram_id: number, telegram_username?: string, referral_code?: string) =>
    api.post<TokenResponse>('/auth/telegram', { telegram_id, telegram_username, referral_code }),

  refresh: (refresh_token: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token }),
}
// END_BLOCK_AUTH_API

// START_BLOCK_USER_API
// User API
export const userApi = {
  getMe: () =>
    api.get<User>('/users/me'),

  getStats: () =>
    api.get<UserStats>('/users/me/stats'),

  updateProfile: (data: { name?: string; language?: string }) =>
    api.put<User>('/users/me', data),

  changePassword: (current_password: string, new_password: string) =>
    api.post('/users/me/change-password', { current_password, new_password }),
}
// END_BLOCK_USER_API

// START_BLOCK_VPN_API
// VPN API
export const vpnApi = {
  getConfig: () =>
    api.get<VPNConfig>('/vpn/config'),

  downloadConfig: () =>
    api.get('/vpn/config/download', {
      responseType: 'blob',
      headers: {
        Accept: CONFIG_DOWNLOAD_MIME_TYPE,
      },
    }),

  getQRCode: () =>
    api.get('/vpn/config/qr', { responseType: 'blob' }),

  getAmneziaQRCode: () =>
    api.get('/vpn/config/qr/amnezia', { responseType: 'blob' }),

  getStats: () =>
    api.get<VPNStats>('/vpn/stats'),

  getNodes: () =>
    api.get<{ nodes: VPNNodeStatus[] }>('/vpn/nodes'),

  getRoutes: () =>
    api.get<{ routes: VPNRouteStatus[] }>('/vpn/routes'),
}
// END_BLOCK_VPN_API

// START_BLOCK_DEVICE_API
export const deviceApi = {
  list: () =>
    api.get<DeviceList>('/devices'),

  create: (data: { name: string; platform?: string }) =>
    api.post<DeviceConfigBundle>('/devices', data),

  getConfig: (deviceId: number) =>
    api.get<DeviceConfigBundle>(`/devices/${deviceId}/config`),

  downloadConfig: (deviceId: number) =>
    api.get(`/devices/${deviceId}/config/download`, {
      responseType: 'blob',
      headers: {
        Accept: CONFIG_DOWNLOAD_MIME_TYPE,
      },
    }),

  getQRCode: (deviceId: number) =>
    api.get(`/devices/${deviceId}/config/qr`, { responseType: 'blob' }),

  getAmneziaQRCode: (deviceId: number) =>
    api.get(`/devices/${deviceId}/config/qr/amnezia`, { responseType: 'blob' }),

  rotate: (deviceId: number) =>
    api.post<DeviceConfigBundle>(`/devices/${deviceId}/rotate`),

  revoke: (deviceId: number) =>
    api.delete<UserDevice>(`/devices/${deviceId}`),
}
// END_BLOCK_DEVICE_API

// START_BLOCK_BILLING_API
// Billing API
export const billingApi = {
  getPlans: () =>
    api.get<Plan[]>('/billing/plans'),

  getSubscription: () =>
    api.get<SubscriptionStatus>('/billing/subscription'),

  createPayment: (plan_id: number) =>
    api.post('/billing/subscribe', { plan_id }),
}
// END_BLOCK_BILLING_API

// START_BLOCK_REFERRAL_API
// Referral API
export const referralApi = {
  getCode: () =>
    api.get('/referrals/code'),

  getStats: () =>
    api.get<ReferralStats>('/referrals/stats'),

  getList: () =>
    api.get<{ items: ReferralListItem[]; total: number }>('/referrals/list'),
}
// END_BLOCK_REFERRAL_API

// START_BLOCK_MTPROTO_API
export const mtprotoApi = {
  getProxy: () =>
    api.get<MTProtoProxyResponse>('/mtproto/proxy'),
}
// END_BLOCK_MTPROTO_API
