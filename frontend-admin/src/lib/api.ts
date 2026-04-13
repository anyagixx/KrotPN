// FILE: frontend-admin/src/lib/api.ts
// VERSION: 1.0.0
// ROLE: RUNTIME
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: HTTP API client with JWT auth, refresh-token interceptor, and typed admin endpoint bindings
//   SCOPE: Axios instance, request/response interceptors, adminApi facade for all backend endpoints
//   DEPENDS: M-010 (frontend-admin), M-006 (backend API), axios, types (AdminNode, AdminRoute, AdminPlan, AdminUser)
//   LINKS: M-010, M-006
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   api - Base axios instance with auth header injection via localStorage
//   response interceptor - Handles 401 with refresh-token retry logic, redirect to /login on failure
//   adminApi - Facade object grouping all admin API endpoints by domain (auth, users, servers, nodes, routes, plans, billing, referrals, devices)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.8.1 - Fixed admin login 404: API_BASE changed from '/api' to '/api/v1' to match backend router prefixes
// END_CHANGE_SUMMARY

import axios from 'axios'
import type {
  AdminNode,
  AdminRoute,
  AdminPlan,
  AdminUser,
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
// Domains: auth, users, stats/analytics, servers, nodes, routes, billing/plans, referrals, devices
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
}
// END_BLOCK: adminApi
