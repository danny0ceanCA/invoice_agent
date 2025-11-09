import { API_BASE, type ApiError } from "./auth";
import type { DistrictProfile } from "./districts";

export interface AdminDistrictPayload {
  company_name: string;
  contact_name: string;
  contact_email: string;
  phone_number: string;
  mailing_address: string;
  district_key?: string;
}

async function adminFetch<T>(
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

export async function listDistricts(accessToken: string): Promise<DistrictProfile[]> {
  return adminFetch<DistrictProfile[]>("/admin/districts", accessToken);
}

export async function createDistrict(
  accessToken: string,
  payload: AdminDistrictPayload,
): Promise<DistrictProfile> {
  return adminFetch<DistrictProfile>("/admin/districts", accessToken, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
