// FILE: frontend-admin/src/types/index.ts
// VERSION: 1.0.0
// ROLE: TYPES
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Shared TypeScript interfaces for admin frontend API contracts
//   SCOPE: AdminUser, AdminDevice, AdminPlan, AdminServer, AdminNode, AdminRoute, MTProto admin/analytics contracts, BillingStats, ReferralStats, SystemHealth, AnalyticsData, PaginatedResponse, NodeForm, RouteForm
//   DEPENDS: M-010 (frontend-admin), M-047 (mtproto-admin-ops), M-058 (mtproto-admin-analytics-ui)
//   LINKS: M-010 (frontend-admin), M-006 (admin-api), M-047, M-058
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AdminUser, AdminDevice, AdminPlan, AdminServer, AdminNode, AdminRoute - Admin entity interfaces
//   AdminMTProtoAssignment, AdminMTProtoListResponse, AdminMTProtoHealth, AdminMTProtoActionResponse - Redacted MTProto admin interfaces
//   AdminMTProtoAnalyticsSummary, AdminMTProtoAssignmentUsage, AdminMTProtoTopUsersResponse, AdminMTProtoPromotionTagState - MTProto analytics interfaces
//   BillingStats, ReferralStats, SystemHealth, AnalyticsData - Analytics interfaces
//   PaginatedResponse - Generic pagination wrapper
//   NodeForm, RouteForm - Form state interfaces for CRUD
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.3.0 - Added Phase-42 MTProto analytics and promotion tag admin contracts
//   LAST_CHANGE: v3.2.1 - Added safe MTProto runtime revoke result to admin action responses
//   LAST_CHANGE: v3.2.0 - Added Phase-33 redacted MTProto admin API contracts
//   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format with START/END blocks
// END_CHANGE_SUMMARY

// START_BLOCK: AdminUser
export interface AdminUser {
  id: number
  email: string
  display_name?: string | null
  role: string
  is_active: boolean
  telegram_username?: string | null
  last_login_at?: string | null
  created_at?: string | null
}
// END_BLOCK: AdminUser

// START_BLOCK: AdminDevice
export interface AdminDevice {
  id: number
  user_id: number
  user_email?: string | null
  user_display_name?: string | null
  name: string
  platform?: string | null
  status: string
  config_version: number
  last_endpoint?: string | null
  last_handshake_at?: string | null
  block_reason?: string | null
  recent_event_types?: string[]
}
// END_BLOCK: AdminDevice

// START_BLOCK: AdminPlan
export interface AdminPlan {
  id: number
  name: string
  description?: string | null
  price: number
  currency: string
  duration_days: number
  device_limit?: number
  features: string[] | string
  is_active: boolean
  is_popular?: boolean
}
// END_BLOCK: AdminPlan

// START_BLOCK: AdminServer
export interface AdminServer {
  id: number
  name: string
  type?: string
  location: string
  country_code: string
  endpoint: string
  port: number
  public_key?: string | null
  is_online: boolean
  is_active: boolean
}
// END_BLOCK: AdminServer

// START_BLOCK: AdminNode
export interface AdminNode {
  id: number
  name: string
  role?: string
  location: string
  country_code: string
  endpoint: string
  port: number
  public_key?: string | null
  private_key?: string | null
  is_online: boolean
  is_active: boolean
  is_entry_node: boolean
  is_exit_node: boolean
  max_clients: number
  current_clients: number
  load_percent: number
}
// END_BLOCK: AdminNode

// START_BLOCK: AdminRoute
export interface AdminRoute {
  id: number
  name: string
  entry_node_id: number
  exit_node_id?: number | null
  entry_node_name: string
  exit_node_name?: string | null
  entry_node_location: string
  exit_node_location?: string | null
  is_active: boolean
  is_default: boolean
  priority: number
  max_clients?: number | null
  current_clients: number
  load_percent: number
  tunnel_status?: string
  tunnel_interface?: string
}
// END_BLOCK: AdminRoute

// START_BLOCK: AdminMTProto
export interface AdminMTProtoAssignment {
  id: number
  assignment_id: number
  user_id: number
  user_email?: string | null
  user_display_name?: string | null
  sni: string
  credential_mode: string
  status: string
  rotation_marker: string
  reissue_required: boolean
  issued_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  superseded_at?: string | null
}

export interface AdminMTProtoListResponse {
  items: AdminMTProtoAssignment[]
  total: number
  offset: number
  limit: number
}

export interface AdminMTProtoHealth {
  status: string
  adapter_name: string
  last_success_at?: string | null
  last_failure_code?: string | null
  last_checked_at?: string | null
}

export interface AdminMTProtoActionResponse {
  assignment: AdminMTProtoAssignment
  runtime_apply?: {
    assignment_id?: number | null
    sni?: string | null
    status: string
    failure_code?: string | null
    safe_message?: string
    applied_at?: string | null
  }
  runtime_revoke?: {
    assignment_id?: number | null
    sni?: string | null
    status: string
    failure_code?: string | null
    safe_message?: string
    applied_at?: string | null
  }
  revoked?: boolean
}

export interface AdminMTProtoTrafficWindow {
  bytes_in: number
  bytes_out: number
  traffic_bytes: number
  connection_count: number
  duration_ms: number
  error_count: number
}

export interface AdminMTProtoAnalyticsSummary {
  issued_total: number
  status_counts: Record<string, number>
  active_connections: number
  last_seen_at?: string | null
  traffic_windows: {
    day: AdminMTProtoTrafficWindow
    week: AdminMTProtoTrafficWindow
    month: AdminMTProtoTrafficWindow
    selected: AdminMTProtoTrafficWindow
  }
  error_count: number
  unknown_sni_count: number
  rejected_sni_count: number
  abuse_signal_count: number
  telemetry_status: string
  availability_proof: {
    req_pq_last_at?: string | null
    status: string
  }
  runtime_health: AdminMTProtoHealth | { status: string }
}

export interface AdminMTProtoUsageEvent {
  id: number
  assignment_id?: number | null
  user_id?: number | null
  event_type: string
  observed_at?: string | null
  sni_masked?: string | null
  ip_hash_prefix?: string | null
  bytes_in: number
  bytes_out: number
  duration_ms: number
  connection_count: number
  error_code?: string | null
  reason_code?: string | null
}

export interface AdminMTProtoAbuseSignal {
  id: number
  assignment_id?: number | null
  user_id?: number | null
  signal_type: string
  severity: string
  observe_only: boolean
  window_start?: string | null
  window_end?: string | null
  metric_value: number
  threshold_value: number
  reason_code: string
}

export interface AdminMTProtoAssignmentUsage {
  assignment: {
    id: number
    user_id: number
    user_email?: string | null
    user_display_name?: string | null
    sni_masked?: string | null
    status: string
    rotation_marker: string
  }
  window_days: number
  last_seen_at?: string | null
  last_req_pq_at?: string | null
  active_connections: number
  connection_count: number
  session_count: number
  active_session_count: number
  duration_ms: number
  bytes_in: number
  bytes_out: number
  error_count: number
  recent_events: AdminMTProtoUsageEvent[]
  abuse_signals: AdminMTProtoAbuseSignal[]
}

export interface AdminMTProtoTopUser {
  user_id: number
  user_email?: string | null
  user_display_name?: string | null
  traffic_bytes: number
  duration_ms: number
  connection_count: number
  error_count: number
}

export interface AdminMTProtoTopUsersResponse {
  items: AdminMTProtoTopUser[]
  metric: string
  days: number
  limit: number
}

export interface AdminMTProtoEventListResponse {
  items: AdminMTProtoUsageEvent[]
  total: number
  offset: number
  limit: number
}

export interface AdminMTProtoAbuseSignalListResponse {
  items: AdminMTProtoAbuseSignal[]
  total: number
  offset: number
  limit: number
}

export interface AdminMTProtoPromotionTagState {
  masked_tag: string
  source: string
  runtime_status: string
  pending_restart: boolean
  updated_by_admin_id?: number | null
  updated_at?: string | null
}
// END_BLOCK: AdminMTProto

// START_BLOCK: BillingStats
export interface BillingStats {
  total_users: number
  active_subscriptions: number
  trial_subscriptions: number
  expired_this_month: number
  revenue_this_month: number
}
// END_BLOCK: BillingStats

// START_BLOCK: SystemHealth
export interface SystemHealth {
  backend: string
  database: string
  redis: string
  vpn_tunnel: string
}
// END_BLOCK: SystemHealth

// START_BLOCK: ReferralStats
export interface ReferralStats {
  total_codes: number
  total_referrals: number
  paid_referrals: number
  conversion_rate: number
}
// END_BLOCK: ReferralStats

// START_BLOCK: AnalyticsDataPoint
export interface AnalyticsDataPoint {
  date: string
  revenue?: number
  count?: number
}
// END_BLOCK: AnalyticsDataPoint

// START_BLOCK: AnalyticsData
export interface AnalyticsData {
  daily: AnalyticsDataPoint[]
}
// END_BLOCK: AnalyticsData

// START_BLOCK: PaginatedResponse
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  pages: number
}
// END_BLOCK: PaginatedResponse

// START_BLOCK: NodeForm
export interface NodeForm {
  name: string
  role: string
  country_code: string
  location: string
  endpoint: string
  port: string | number
  public_key: string
  private_key: string
  is_active: boolean
  is_online: boolean
  max_clients: string | number
}
// END_BLOCK: NodeForm

// START_BLOCK: RouteForm
export interface RouteForm {
  name: string
  entry_node_id: string
  exit_node_id: string
  is_active: boolean
  is_default: boolean
  priority: string | number
  max_clients: string
}
// END_BLOCK: RouteForm
