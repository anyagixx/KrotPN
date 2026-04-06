// FILE: frontend/src/lib/api.ts
// VERSION: 1.0.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Axios API client with auth interceptors, token refresh logic, and typed API service modules
//   SCOPE: HTTP client setup, request/response interceptors, auto token refresh, API namespaces (auth, user, vpn, device, billing, referral)
//   DEPENDS: M-002 (users auth), M-003 (vpn), M-004 (billing), M-005 (referrals)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   api - Axios instance with interceptors
//   User, TokenResponse, VPNConfig, UserDevice, DeviceList, DeviceConfigBundle - Types
//   VPNStats, VPNNodeStatus, VPNRouteStatus, UserStats - Types
//   Plan, SubscriptionStatus, ReferralStats, ReferralListItem - Types
//   authApi - Login, register, telegram auth, refresh
//   userApi - Get me, stats, update profile, change password
//   vpnApi - Config, download, QR, stats, nodes, routes
//   deviceApi - List, create, rotate, revoke
//   billingApi - Get plans, subscription, create payment
//   referralApi - Get code, stats, list
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_API_CLIENT
import axios from 'axios'

const API_BASE = '/api/v1'

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
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
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

          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)

          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
          return api(originalRequest)
        } catch {
          // Refresh failed, clear tokens
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      } else {
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
  name: string
  price: number
  duration_days: number
  features: string[]
  is_active: boolean
}

export interface SubscriptionStatus {
  has_subscription: boolean
  is_active: boolean
  is_trial: boolean
  plan_name: string | null
  days_left: number
  expires_at: string | null
  is_recurring: boolean
}

export interface ReferralStats {
  total_referrals: number
  bonus_days_earned: number
  paid_referrals?: number
}

export interface ReferralListItem {
  id: number
  bonus_given: boolean
  bonus_days: number
  created_at: string
  first_payment_at: string | null
}

// START_BLOCK_AUTH_API
// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),

  register: (email: string, password: string, referral_code?: string) =>
    api.post<TokenResponse>('/auth/register', { email, password, referral_code }),

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
    api.get('/vpn/config/download', { responseType: 'blob' }),

  getQRCode: () =>
    api.get('/vpn/config/qr', { responseType: 'blob' }),

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
