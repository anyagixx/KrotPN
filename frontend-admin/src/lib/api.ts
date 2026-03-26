import axios from 'axios'

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
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      window.location.href = '/login'
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
  
  updateUser: (id: number, data: any) =>
    api.put(`/admin/users/${id}`, data),
  
  getServers: () =>
    api.get('/admin/servers'),

  getNodes: () =>
    api.get('/admin/nodes'),

  createNode: (data: any) =>
    api.post('/admin/nodes', data),

  updateNode: (id: number, data: any) =>
    api.put(`/admin/nodes/${id}`, data),

  deleteNode: (id: number) =>
    api.delete(`/admin/nodes/${id}`),

  getRoutes: () =>
    api.get('/admin/routes'),

  createRoute: (data: any) =>
    api.post('/admin/routes', data),

  updateRoute: (id: number, data: any) =>
    api.put(`/admin/routes/${id}`, data),

  deleteRoute: (id: number) =>
    api.delete(`/admin/routes/${id}`),
  
  createServer: (data: any) =>
    api.post('/admin/servers', data),
  
  updateServer: (id: number, data: any) =>
    api.put(`/admin/servers/${id}`, data),
  
  deleteServer: (id: number) =>
    api.delete(`/admin/servers/${id}`),
  
  getPlans: () =>
    api.get('/admin/billing/plans'),
  
  createPlan: (data: any) =>
    api.post('/admin/billing/plans', data),
  
  updatePlan: (id: number, data: any) =>
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

  createDomainRouteRule: (data: any) =>
    api.post('/routing/policy/domains', data),

  updateDomainRouteRule: (id: number, data: any) =>
    api.put(`/routing/policy/domains/${id}`, data),

  deleteDomainRouteRule: (id: number) =>
    api.delete(`/routing/policy/domains/${id}`),

  getCidrRouteRules: () =>
    api.get('/routing/policy/cidrs'),

  createCidrRouteRule: (data: any) =>
    api.post('/routing/policy/cidrs', data),

  updateCidrRouteRule: (id: number, data: any) =>
    api.put(`/routing/policy/cidrs/${id}`, data),

  deleteCidrRouteRule: (id: number) =>
    api.delete(`/routing/policy/cidrs/${id}`),

  getPolicyDnsBindings: () =>
    api.get('/routing/policy/dns-bindings'),

  explainRouteDecision: (address: string) =>
    api.post('/routing/policy/explain', { address }),
}
