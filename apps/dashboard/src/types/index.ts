export type Platform =
  | "windows"
  | "linux"
  | "android"
  | "ios"
  | "simulator"
  | "unknown";

export interface GroupQuotaSummary {
  group_id: string;
  group_name: string;
  quota_bytes: number;
  used_bytes: number;
  remaining_bytes: number;
  percentage_used: number;
  period_starts_at: string | null;
  period_ends_at: string | null;
  device_count: number;
  highest_threshold: number | null;
  measurement_quality: string;
  has_missing_measurements: boolean;
}

export interface UsagePoint {
  bucket: string;
  received_bytes: number;
  sent_bytes: number;
  total_bytes: number;
}

export interface DeviceHealth {
  id: string;
  name: string;
  platform: Platform;
  group_name: string | null;
  last_seen_at: string | null;
  minutes_since_report: number | null;
  measurement_quality: string;
}

export interface DashboardEvent {
  id: string;
  event_type: string;
  created_at: string;
  severity: "info" | "warning" | "critical";
  message: string | null;
  group_id: string | null;
  device_id: string | null;
}

export interface DashboardSummary {
  generated_at: string;
  active_period_starts_at: string | null;
  active_period_ends_at: string | null;
  device_count: number;
  reporting_device_count: number;
  stale_device_count: number;
  revoked_device_count: number;
  total_received_bytes: number;
  total_sent_bytes: number;
  total_bytes: number;
  groups: GroupQuotaSummary[];
  recent_events: DashboardEvent[];
  stale_devices: DeviceHealth[];
  measurement_warnings: string[];
  usage_series: UsagePoint[];
}

export interface Device {
  id: string;
  name: string;
  platform: Platform;
  agent_version: string | null;
  created_at: string;
  last_seen_at: string | null;
  is_active: boolean;
  measurement_scope: string;
  measurement_quality: string;
  last_sequence: number;
  group_id: string | null;
  group_name: string | null;
  is_stale: boolean;
}

export interface DeviceDetail extends Device {
  capabilities: Record<string, unknown>;
  current_period_received: number;
  current_period_sent: number;
  interfaces: string[];
  recent_warnings: string[];
}

export interface Group {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  reset_day: number;
  device_count: number;
}

export interface GroupUsage {
  group_id: string;
  group_name: string;
  summary: GroupQuotaSummary;
  series: UsagePoint[];
}

export interface EventItem {
  id: string;
  event_type: string;
  created_at: string;
  device_id: string | null;
  group_id: string | null;
  quota_period_id: string | null;
  severity: string;
  message: string | null;
  details: Record<string, unknown>;
}

export interface EnrollmentCodeCreated {
  id: string;
  code: string;
  label: string | null;
  expires_at: string;
  group_id: string | null;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  expires_at: string;
}