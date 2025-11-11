import { API_BASE, type ApiError } from "./auth";
import type { PostalAddress } from "./common";

export interface DistrictProfile {
  id: number;
  company_name: string;
  contact_name: string | null;
  contact_email: string | null;
  phone_number: string | null;
  mailing_address: PostalAddress | null;
  district_key: string;
  is_profile_complete: boolean;
}

export interface DistrictProfilePayload {
  company_name: string;
  contact_name: string;
  contact_email: string;
  phone_number: string;
  mailing_address: PostalAddress;
}

export interface DistrictMembershipEntry {
  district_id: number;
  company_name: string;
  district_key: string;
  is_active: boolean;
}

export interface DistrictMembershipCollection {
  active_district_id: number | null;
  memberships: DistrictMembershipEntry[];
}

export interface DistrictVendorStudent {
  id: number;
  name: string;
  service: string | null;
  amount: number;
  pdf_url: string | null;
  timesheet_url: string | null;
}

export interface DistrictVendorInvoice {
  id: number;
  month: string;
  month_index: number | null;
  year: number;
  status: string;
  total: number;
  processed_on: string | null;
  download_url: string | null;
  pdf_url: string | null;
  timesheet_csv_url: string | null;
  students: DistrictVendorStudent[];
}

export interface DistrictVendorMetrics {
  latest_year: number | null;
  invoices_this_year: number;
  approved_count: number;
  needs_action_count: number;
  total_spend: number;
  outstanding_spend: number;
}

export interface DistrictVendorLatestInvoice {
  month: string;
  year: number;
  total: number;
  status: string;
}

export interface DistrictVendorProfile {
  id: number;
  name: string;
  contact_name: string | null;
  contact_email: string | null;
  phone_number: string | null;
  remit_to_address: PostalAddress | null;
  metrics: DistrictVendorMetrics;
  health_label: string | null;
  latest_invoice: DistrictVendorLatestInvoice | null;
  invoices: Record<number, DistrictVendorInvoice[]>;
}

export interface DistrictVendorOverview {
  generated_at: string;
  vendors: DistrictVendorProfile[];
}

async function districtFetch<T>(
  path: string,
  accessToken: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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

export async function fetchDistrictProfile(accessToken: string): Promise<DistrictProfile> {
  return districtFetch<DistrictProfile>("/districts/me", accessToken);
}

export async function updateDistrictProfile(
  accessToken: string,
  payload: DistrictProfilePayload,
): Promise<DistrictProfile> {
  return districtFetch<DistrictProfile>("/districts/me", accessToken, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchDistrictVendors(
  accessToken: string,
): Promise<DistrictVendorOverview> {
  return districtFetch<DistrictVendorOverview>("/districts/vendors", accessToken);
}

export async function fetchDistrictMemberships(
  accessToken: string,
): Promise<DistrictMembershipCollection> {
  return districtFetch<DistrictMembershipCollection>("/districts/memberships", accessToken);
}

export async function addDistrictMembership(
  accessToken: string,
  districtKey: string,
): Promise<DistrictMembershipCollection> {
  return districtFetch<DistrictMembershipCollection>("/districts/memberships", accessToken, {
    method: "POST",
    body: JSON.stringify({ district_key: districtKey }),
  });
}

export async function activateDistrictMembership(
  accessToken: string,
  districtId: number,
): Promise<DistrictMembershipCollection> {
  return districtFetch<DistrictMembershipCollection>(
    `/districts/memberships/${districtId}/activate`,
    accessToken,
    {
      method: "POST",
    },
  );
}
