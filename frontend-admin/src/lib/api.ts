import axios from 'axios'
import type {
  AdminNode,
  AdminRoute,
  AdminPlan,
  RoutePolicyRule,
  AdminUser,
} from '../types'

const API_BASE = '/api'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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

export const adminApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),

  getCurrentUser: () =>
    api.get('/users/me'),
  
  getStats: () =>
    api.get('/admin/stats'),
  
  getRevenueAnalytics: (days: number = 30) =>
    api.get(`/admin/analytics/revenue?days=${days}`),
  
  getUsersAnalytics: (days: number = 30) =>
    api.get(`/admin/analytics/users?days=${days}`),
  
  getUsers: (page = 1, search = '') =>
    api.get(`/admin/users?page=${page}&search=${search}`),
  
  getUser: (id: number) =>
    api.get(`/admin/users/${id}`),
  
  updateUser: (id: number, data: Partial<AdminUser>) =>
    api.put(`/admin/users/${id}`, data),
  
  getServers: () =>
    api.get('/admin/servers'),

  getNodes: () =>
    api.get('/admin/nodes'),

  createNode: (data: Partial<AdminNode>) =>
    api.post('/admin/nodes', data),

  updateNode: (id: number, data: Partial<AdminNode>) =>
    api.put(`/admin/nodes/${id}`, data),

  deleteNode: (id: number) =>
    api.delete(`/admin/nodes/${id}`),

  getRoutes: () =>
    api.get('/admin/routes'),

  createRoute: (data: Partial<AdminRoute>) =>
    api.post('/admin/routes', data),

  updateRoute: (id: number, data: Partial<AdminRoute>) =>
    api.put(`/admin/routes/${id}`, data),

  deleteRoute: (id: number) =>
    api.delete(`/admin/routes/${id}`),
  
  createServer: (data: Partial<AdminNode>) =>
    api.post('/admin/servers', data),
  
  updateServer: (id: number, data: Partial<AdminNode>) =>
    api.put(`/admin/servers/${id}`, data),
  
  deleteServer: (id: number) =>
    api.delete(`/admin/servers/${id}`),
  
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
  
  getReferralStats: () =>
    api.get('/admin/referrals/stats'),
  
  getSystemHealth: () =>
    api.get('/admin/system/health'),

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

  getDomainRouteRules: () =>
    api.get('/routing/policy/domains'),

  createDomainRouteRule: (data: Partial<RoutePolicyRule>) =>
    api.post('/routing/policy/domains', data),

  updateDomainRouteRule: (id: number, data: Partial<RoutePolicyRule>) =>
    api.put(`/routing/policy/domains/${id}`, data),

  deleteDomainRouteRule: (id: number) =>
    api.delete(`/routing/policy/domains/${id}`),

  getCidrRouteRules: () =>
    api.get('/routing/policy/cidrs'),

  createCidrRouteRule: (data: Partial<RoutePolicyRule>) =>
    api.post('/routing/policy/cidrs', data),

  updateCidrRouteRule: (id: number, data: Partial<RoutePolicyRule>) =>
    api.put(`/routing/policy/cidrs/${id}`, data),

  deleteCidrRouteRule: (id: number) =>
    api.delete(`/routing/policy/cidrs/${id}`),

  getPolicyDnsBindings: () =>
    api.get('/routing/policy/dns-bindings'),

  explainRouteDecision: (address: string) =>
    api.post('/routing/policy/explain', { address }),
}
