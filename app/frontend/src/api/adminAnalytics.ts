import { API_BASE, type ApiError } from "./auth";

export interface AdminCacheEntry {
  key: string;
  ttl_seconds: number | null;
  approx_bytes: number | null;
  has_payload?: boolean;
  district_key?: string | null;
  created_at?: string | null;
  last_accessed?: string | null;
}

export interface AdminCacheResponse {
  items: AdminCacheEntry[];
  total_keys: number;
}

export interface MaterializedReportItem {
  id: number;
  district_key: string | null;
  cache_key?: string | null;
  report_kind: string | null;
  primary_entity: string | null;
  created_at: string | null;
  last_accessed_at: string | null;
  payload_preview?: Record<string, unknown> | null;
  payload?: Record<string, unknown> | null;
}

export interface MaterializedReportsResponse {
  items: MaterializedReportItem[];
  total: number;
}

export interface PrefetchHistoryEntry {
  district_key?: string | null;
  timestamp?: string | null;
  queries?: string[] | string | null;
  reason?: string | null;
}

export interface PrefetchHistoryResponse {
  items: PrefetchHistoryEntry[];
}

async function adminAnalyticsFetch<T>(
  path: string,
  accessToken: string,
  init?: RequestInit,
): Promise<T> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_BASE}${normalizedPath}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${accessToken}`,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    const error: ApiError = new Error(
      message || `Request to ${path} failed with status ${response.status}`,
    );
    error.status = response.status;
    error.statusText = response.statusText;
    throw error;
  }

  return response.json() as Promise<T>;
}

export async function fetchAdminCacheEntries(
  accessToken: string,
): Promise<AdminCacheResponse> {
  return adminAnalyticsFetch<AdminCacheResponse>("/admin/analytics/cache", accessToken);
}

export async function fetchAdminMaterializedReports(
  accessToken: string,
  params?: {
    district_key?: string;
    report_kind?: string;
    primary_entity?: string;
    limit?: number;
    offset?: number;
    raw?: boolean;
  },
): Promise<MaterializedReportsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.district_key) searchParams.set("district_key", params.district_key);
  if (params?.report_kind) searchParams.set("report_kind", params.report_kind);
  if (params?.primary_entity) searchParams.set("primary_entity", params.primary_entity);
  if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") searchParams.set("offset", String(params.offset));
  if (typeof params?.raw === "boolean") searchParams.set("raw", String(params.raw));

  const qs = searchParams.toString();
  const path = `/admin/analytics/materialized-reports${qs ? `?${qs}` : ""}`;
  return adminAnalyticsFetch<MaterializedReportsResponse>(path, accessToken);
}

export async function fetchAdminPrefetchHistory(
  accessToken: string,
): Promise<PrefetchHistoryResponse> {
  return adminAnalyticsFetch<PrefetchHistoryResponse>("/admin/analytics/prefetch", accessToken);
}
