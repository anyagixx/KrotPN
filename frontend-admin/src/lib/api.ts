// FILE: frontend-admin/src/lib/api.ts
// VERSION: 1.1.0
// ROLE: RUNTIME
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: HTTP API client with JWT auth, refresh-token interceptor, and typed admin endpoint bindings
//   SCOPE: Axios instance, request/response interceptors, adminApi facade for all backend endpoints including VPN abuse alerts and MTProto admin ops/analytics/manual delivery
//   DEPENDS: M-010 (frontend-admin), M-006 (backend API), M-047 (MTProto admin ops), M-058 (MTProto analytics UI), M-081 (VPN device abuse alert inbox), M-082 (manual external MTProto delivery), axios, types
//   LINKS: M-010, M-006, M-047, M-058, M-081, M-082
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   api - Base axios instance with auth header injection via localStorage
//   response interceptor - Handles 401 with refresh-token retry logic, redirect to /login on failure
//   adminApi - Facade object grouping all admin API endpoints by domain (auth, users, servers, nodes, routes, plans, billing, referrals, devices, VPN abuse alerts, MTProto)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.7.0 - Added Phase-80 manual external MTProto pool and delivery mode endpoint bindings.
//   LAST_CHANGE: v3.6.0 - Added Phase-78 VPN device abuse alert inbox endpoint bindings.
//   LAST_CHANGE: v3.5.0 - Added pagination offsets for MTProto assignment inventory and user investigation search.
//   LAST_CHANGE: v3.4.0 - Added Phase-43 MTProto alert, user investigation, timeseries, resource, and storage endpoint bindings
//   LAST_CHANGE: v3.3.0 - Added Phase-42 MTProto analytics and promotion tag endpoint bindings
//   LAST_CHANGE: v3.2.0 - Added Phase-33 MTProto admin endpoint bindings
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.8.1 - Fixed admin login 404: API_BASE changed from '/api' to '/api/v1' to match backend router prefixes
// END_CHANGE_SUMMARY

import axios from 'axios'
import type {
  AdminMTProtoAssignment,
  AdminMTProtoActionResponse,
  AdminMTProtoAlert,
  AdminMTProtoAlertListResponse,
  AdminMTProtoAbuseSignalListResponse,
  AdminMTProtoAnalyticsSummary,
  AdminMTProtoAssignmentUsage,
  AdminMTProtoDeliveryMode,
  AdminMTProtoDeliveryModeState,
  AdminMTProtoEventListResponse,
  AdminMTProtoHealth,
  AdminMTProtoListResponse,
  AdminMTProtoManualProxy,
  AdminMTProtoManualProxyListResponse,
  AdminMTProtoPromotionTagState,
  AdminMTProtoRuntimeResourceSnapshot,
  AdminMTProtoStorageBudget,
  AdminMTProtoTimeseriesResponse,
  AdminMTProtoTopUsersResponse,
  AdminMTProtoUserInvestigation,
  AdminMTProtoUserSearchResponse,
  AdminNode,
  AdminRoute,
  AdminPlan,
  AdminUser,
  AdminVPNDeviceAbuseAlert,
  AdminVPNDeviceAbuseAlertListResponse,
} from '../types'

const API_BASE = '/api/v1'

// START_BLOCK: api
// Base axios instance with JWT authorization header injection
// Reads admin_token from localStorage and sets Authorization header on every request
export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})
// END_BLOCK: api

// START_BLOCK: authInterceptor
// Request interceptor: attaches Bearer token from localStorage to outgoing requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Response interceptor: automatic token refresh on 401, fallback to /login
// STRATEGY: Single retry with _retry flag to prevent infinite loops
// SIDE_EFFECTS: May redirect window.location to /login if refresh fails or no refresh_token
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('admin_refresh_token')
      if (refreshToken) {
        try {
          const refreshApi = axios.create({ baseURL: API_BASE })
          const { data } = await refreshApi.post('/auth/refresh', {
            refresh_token: refreshToken,
          })

          localStorage.setItem('admin_token', data.access_token)
          localStorage.setItem('admin_refresh_token', data.refresh_token)

          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
          return api(originalRequest)
        } catch {
          localStorage.removeItem('admin_token')
          localStorage.removeItem('admin_refresh_token')
          window.location.href = '/login'
        }
      } else {
        localStorage.removeItem('admin_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
// END_BLOCK: authInterceptor

// START_BLOCK: adminApi
// Facade object exposing all admin backend endpoints grouped by domain
// Domains: auth, users, stats/analytics, servers, nodes, routes, billing/plans, referrals, devices, VPN abuse alerts, MTProto
// DEPENDS: /api/* backend routes (M-006), types (AdminNode, AdminRoute, AdminPlan, AdminUser)
export const adminApi = {
  // Auth
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),

  getCurrentUser: () =>
    api.get('/users/me'),

  // Stats & Analytics
  getStats: () =>
    api.get('/admin/stats'),

  getRevenueAnalytics: (days: number = 30) =>
    api.get(`/admin/analytics/revenue?days=${days}`),

  getUsersAnalytics: (days: number = 30) =>
    api.get(`/admin/analytics/users?days=${days}`),

  // Users
  getUsers: (page = 1, search = '') =>
    api.get(`/admin/users?page=${page}&search=${search}`),

  getUser: (id: number) =>
    api.get(`/admin/users/${id}`),

  updateUser: (id: number, data: Partial<AdminUser>) =>
    api.put(`/admin/users/${id}`, data),

  // Servers
  getServers: () =>
    api.get('/admin/servers'),

  createServer: (data: Partial<AdminNode>) =>
    api.post('/admin/servers', data),

  updateServer: (id: number, data: Partial<AdminNode>) =>
    api.put(`/admin/servers/${id}`, data),

  deleteServer: (id: number) =>
    api.delete(`/admin/servers/${id}`),

  // Nodes
  getNodes: () =>
    api.get('/admin/nodes'),

  createNode: (data: Partial<AdminNode>) =>
    api.post('/admin/nodes', data),

  updateNode: (id: number, data: Partial<AdminNode>) =>
    api.put(`/admin/nodes/${id}`, data),

  deleteNode: (id: number) =>
    api.delete(`/admin/nodes/${id}`),

  // Routes
  getRoutes: () =>
    api.get('/admin/routes'),

  createRoute: (data: Partial<AdminRoute>) =>
    api.post('/admin/routes', data),

  updateRoute: (id: number, data: Partial<AdminRoute>) =>
    api.put(`/admin/routes/${id}`, data),

  deleteRoute: (id: number) =>
    api.delete(`/admin/routes/${id}`),

  // Billing / Plans
  getPlans: () =>
    api.get('/admin/billing/plans'),

  createPlan: (data: Partial<AdminPlan>) =>
    api.post('/admin/billing/plans', data),

  updatePlan: (id: number, data: Partial<AdminPlan>) =>
    api.put(`/admin/billing/plans/${id}`, data),

  deletePlan: (id: number) =>
    api.delete(`/admin/billing/plans/${id}`),

  getBillingStats: () =>
    api.get('/admin/billing/stats'),

  // Referrals
  getReferralStats: () =>
    api.get('/admin/referrals/stats'),

  // System
  getSystemHealth: () =>
    api.get('/admin/system/health'),

  // Devices (peer control / anti-sharing)
  getDevices: (search = '') =>
    api.get(`/admin/devices?search=${encodeURIComponent(search)}`),

  blockDevice: (id: number) =>
    api.post(`/admin/devices/${id}/block`),

  unblockDevice: (id: number) =>
    api.post(`/admin/devices/${id}/unblock`),

  rotateDevice: (id: number) =>
    api.post(`/admin/devices/${id}/rotate`),

  revokeDevice: (id: number) =>
    api.delete(`/admin/devices/${id}`),

  // VPN device abuse alert inbox
  getVPNDeviceAbuseAlerts: (status = 'open', limit = 50, offset = 0) => {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (status) query.set('status', status)
    return api.get<AdminVPNDeviceAbuseAlertListResponse>(`/admin/vpn/abuse/alerts?${query.toString()}`)
  },

  getVPNDeviceAbuseAlert: (id: number) =>
    api.get<AdminVPNDeviceAbuseAlert>(`/admin/vpn/abuse/alerts/${id}`),

  resolveVPNDeviceAbuseAlert: (id: number, note = 'resolved_by_admin') =>
    api.post<AdminVPNDeviceAbuseAlert>(`/admin/vpn/abuse/alerts/${id}/resolve`, { confirm: true, note }),

  rotateVPNDeviceAbuseAlert: (id: number) =>
    api.post<AdminVPNDeviceAbuseAlert>(`/admin/vpn/abuse/alerts/${id}/rotate-device`, { confirm: true }),

  blockVPNDeviceAbuseAlert: (id: number) =>
    api.post<AdminVPNDeviceAbuseAlert>(`/admin/vpn/abuse/alerts/${id}/block-device`, { confirm: true }),

  // MTProto admin ops
  getMTProtoAssignments: (search = '', status = '', offset = 0, limit = 50) => {
    const params = new URLSearchParams()
    if (search.trim()) params.set('search', search.trim())
    if (status) params.set('status', status)
    params.set('offset', String(offset))
    params.set('limit', String(limit))
    const query = params.toString()
    return api.get<AdminMTProtoListResponse>(`/admin/mtproto/assignments${query ? `?${query}` : ''}`)
  },

  getMTProtoAssignment: (id: number) =>
    api.get<AdminMTProtoAssignment>(`/admin/mtproto/assignments/${id}`),

  getMTProtoHealth: () =>
    api.get<AdminMTProtoHealth>('/admin/mtproto/health'),

  getMTProtoManualProxies: (search = '', status = '', offset = 0, limit = 100) => {
    const params = new URLSearchParams()
    if (search.trim()) params.set('search', search.trim())
    if (status) params.set('status', status)
    params.set('offset', String(offset))
    params.set('limit', String(limit))
    const query = params.toString()
    return api.get<AdminMTProtoManualProxyListResponse>(`/admin/mtproto/manual-proxies${query ? `?${query}` : ''}`)
  },

  createMTProtoManualProxy: (data: {
    name: string
    server: string
    port: number
    secret: string
    priority?: number
    notes?: string | null
  }) =>
    api.post<AdminMTProtoManualProxy>('/admin/mtproto/manual-proxies', data),

  updateMTProtoManualProxy: (id: number, data: {
    name?: string
    server?: string
    port?: number
    secret?: string
    priority?: number
    notes?: string | null
  }) =>
    api.patch<AdminMTProtoManualProxy>(`/admin/mtproto/manual-proxies/${id}`, data),

  activateMTProtoManualProxy: (id: number) =>
    api.post<AdminMTProtoManualProxy>(`/admin/mtproto/manual-proxies/${id}/activate`, { confirm: true }),

  disableMTProtoManualProxy: (id: number) =>
    api.post<AdminMTProtoManualProxy>(`/admin/mtproto/manual-proxies/${id}/disable`, { confirm: true }),

  getMTProtoDeliveryMode: () =>
    api.get<AdminMTProtoDeliveryModeState>('/admin/mtproto/delivery-mode'),

  updateMTProtoDeliveryMode: (mode: AdminMTProtoDeliveryMode) =>
    api.put<AdminMTProtoDeliveryModeState>('/admin/mtproto/delivery-mode', { mode, confirm: true }),

  getMTProtoAnalyticsSummary: (days = 30) =>
    api.get<AdminMTProtoAnalyticsSummary>(`/admin/mtproto/analytics/summary?days=${days}`),

  getMTProtoAssignmentUsage: (id: number, days = 30) =>
    api.get<AdminMTProtoAssignmentUsage>(`/admin/mtproto/assignments/${id}/usage?days=${days}`),

  getMTProtoEvents: (params: { assignment_id?: number; event_type?: string; days?: number; offset?: number; limit?: number } = {}) => {
    const query = new URLSearchParams()
    if (params.assignment_id) query.set('assignment_id', String(params.assignment_id))
    if (params.event_type) query.set('event_type', params.event_type)
    if (params.days) query.set('days', String(params.days))
    if (params.offset) query.set('offset', String(params.offset))
    if (params.limit) query.set('limit', String(params.limit))
    const suffix = query.toString()
    return api.get<AdminMTProtoEventListResponse>(`/admin/mtproto/analytics/events${suffix ? `?${suffix}` : ''}`)
  },

  getMTProtoTopUsers: (metric = 'traffic', days = 30, limit = 10) =>
    api.get<AdminMTProtoTopUsersResponse>(`/admin/mtproto/analytics/top-users?metric=${metric}&days=${days}&limit=${limit}`),

  getMTProtoAbuseSignals: (days = 30, assignmentId?: number) => {
    const query = new URLSearchParams({ days: String(days), limit: '20' })
    if (assignmentId) query.set('assignment_id', String(assignmentId))
    return api.get<AdminMTProtoAbuseSignalListResponse>(`/admin/mtproto/analytics/abuse-signals?${query.toString()}`)
  },

  getMTProtoTimeseries: (params: { bucket?: string; days?: number; assignment_id?: number } = {}) => {
    const query = new URLSearchParams()
    query.set('bucket', params.bucket || 'day')
    query.set('days', String(params.days || 30))
    if (params.assignment_id) query.set('assignment_id', String(params.assignment_id))
    return api.get<AdminMTProtoTimeseriesResponse>(`/admin/mtproto/analytics/timeseries?${query.toString()}`)
  },

  searchMTProtoUsers: (queryText = '', limit = 25, offset = 0) => {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (queryText.trim()) query.set('query', queryText.trim())
    return api.get<AdminMTProtoUserSearchResponse>(`/admin/mtproto/analytics/users/search?${query.toString()}`)
  },

  getMTProtoUserUsage: (assignmentId: number, days = 90) =>
    api.get<AdminMTProtoUserInvestigation>(`/admin/mtproto/analytics/users/${assignmentId}/usage?days=${days}`),

  getMTProtoResourceMetrics: () =>
    api.get<AdminMTProtoRuntimeResourceSnapshot>('/admin/mtproto/analytics/resource-metrics'),

  getMTProtoStorageBudget: () =>
    api.get<AdminMTProtoStorageBudget>('/admin/mtproto/analytics/storage-budget'),

  getMTProtoAlerts: (status = '', limit = 50) => {
    const query = new URLSearchParams({ limit: String(limit) })
    if (status) query.set('status', status)
    return api.get<AdminMTProtoAlertListResponse>(`/admin/mtproto/analytics/alerts?${query.toString()}`)
  },

  acknowledgeMTProtoAlert: (alertId: number) =>
    api.post<AdminMTProtoAlert>(`/admin/mtproto/analytics/alerts/${alertId}/acknowledge`, { confirm: true }),

  resolveMTProtoAlert: (alertId: number) =>
    api.post<AdminMTProtoAlert>(`/admin/mtproto/analytics/alerts/${alertId}/resolve`, { confirm: true }),

  disableMTProtoAlertProxy: (alertId: number) =>
    api.post(`/admin/mtproto/analytics/alerts/${alertId}/disable-proxy`, { confirm: true }),

  blockMTProtoAlertIP: (alertId: number, ipObservationId: number, ttlHours = 24) =>
    api.post(`/admin/mtproto/analytics/alerts/${alertId}/block-ip`, {
      ip_observation_id: ipObservationId,
      ttl_hours: ttlHours,
      confirm: true,
      confirm_risk: true,
    }),

  getMTProtoPromotionTag: () =>
    api.get<AdminMTProtoPromotionTagState>('/admin/mtproto/promotion-tag'),

  updateMTProtoPromotionTag: (tag: string) =>
    api.put<AdminMTProtoPromotionTagState>('/admin/mtproto/promotion-tag', { tag, confirm: true }),

  reissueMTProtoAssignment: (id: number) =>
    api.post<AdminMTProtoActionResponse>(`/admin/mtproto/assignments/${id}/reissue`, { confirm: true }),

  revokeMTProtoAssignment: (id: number) =>
    api.post<AdminMTProtoActionResponse>(`/admin/mtproto/assignments/${id}/revoke`, { confirm: true }),
}
// END_BLOCK: adminApi
