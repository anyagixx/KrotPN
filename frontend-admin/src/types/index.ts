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

export interface BillingStats {
  total_users: number
  active_subscriptions: number
  trial_subscriptions: number
  expired_this_month: number
  revenue_this_month: number
}

export interface RoutePolicyRule {
  id: number
  domain?: string
  cidr?: string
  normalized_domain?: string
  normalized_cidr?: string
  route_target: string
  priority: number
  description?: string
  is_active: boolean
}

export interface DNSBinding {
  id: number
  normalized_domain: string
  resolved_ip: string
  route_target: string
  ttl?: number
  updated_at?: string
}

export interface SystemHealth {
  backend: string
  database: string
  redis: string
  vpn_tunnel: string
}

export interface ReferralStats {
  total_codes: number
  total_referrals: number
  paid_referrals: number
  conversion_rate: number
}

export interface AnalyticsDataPoint {
  date: string
  revenue?: number
  count?: number
}

export interface AnalyticsData {
  daily: AnalyticsDataPoint[]
}

export interface ExplainRouteResult {
  route_target: string
  decision_reason: string
  trace_marker: string
  rule_id?: number | null
  normalized_domain?: string
  resolved_ip?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  pages: number
}

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

export interface RouteForm {
  name: string
  entry_node_id: string
  exit_node_id: string
  is_active: boolean
  is_default: boolean
  priority: string | number
  max_clients: string
}

export interface RouteForm {
  name: string
  entry_node_id: string
  exit_node_id: string
  is_active: boolean
  is_default: boolean
  priority: string | number
  max_clients: string
}
