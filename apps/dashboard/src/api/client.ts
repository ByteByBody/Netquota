// Thin typed API client. The administrator token lives in localStorage; agent
// and router credentials never reach the browser.
import type {
  DashboardSummary,
  Device,
  DeviceDetail,
  EnrollmentCodeCreated,
  EventItem,
  Group,
  GroupUsage,
  TokenOut,
  UsagePoint,
} from "../types";

const TOKEN_KEY = "netquota.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/v1${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      (body && (body.detail || body.message)) || `Request failed (${res.status})`;
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body as T;
}

export const api = {
  async login(username: string, password: string): Promise<TokenOut> {
    return request<TokenOut>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },
  async logout(): Promise<void> {
    await request<void>("/auth/logout", { method: "POST" });
    setToken(null);
  },
  async summary(): Promise<DashboardSummary> {
    return request<DashboardSummary>("/dashboard/summary");
  },
  async devices(): Promise<Device[]> {
    return request<Device[]>("/devices");
  },
  async device(id: string): Promise<DeviceDetail> {
    return request<DeviceDetail>(`/devices/${id}`);
  },
  async patchDevice(id: string, patch: Record<string, unknown>): Promise<Device> {
    return request<Device>(`/devices/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  async revokeDevice(id: string): Promise<Device> {
    return request<Device>(`/devices/${id}/revoke`, { method: "POST" });
  },
  async groups(): Promise<Group[]> {
    return request<Group[]>("/groups");
  },
  async createGroup(payload: Record<string, unknown>): Promise<Group> {
    return request<Group>("/groups", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async patchGroup(id: string, patch: Record<string, unknown>): Promise<Group> {
    return request<Group>(`/groups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  async deleteGroup(id: string): Promise<void> {
    await request<void>(`/groups/${id}`, { method: "DELETE" });
  },
  async assignDevice(groupId: string, deviceId: string): Promise<Group> {
    return request<Group>(`/groups/${groupId}/devices/${deviceId}`, {
      method: "POST",
    });
  },
  async groupUsage(id: string): Promise<GroupUsage> {
    return request<GroupUsage>(`/groups/${id}/usage`);
  },
  async deviceUsage(id: string): Promise<{
    device_id: string;
    group_id?: string;
    series: UsagePoint[];
    summary: {
      used_bytes: number;
      period_starts_at: string;
      period_ends_at: string;
    } | null;
  }> {
    return request(`/devices/${id}/usage`);
  },
  async events(params: Record<string, string> = {}): Promise<EventItem[]> {
    const qs = new URLSearchParams(params).toString();
    return request<EventItem[]>(`/events${qs ? `?${qs}` : ""}`);
  },
  async createEnrollmentCode(
    payload: Record<string, unknown>,
  ): Promise<EnrollmentCodeCreated> {
    return request<EnrollmentCodeCreated>("/enrollment/codes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};