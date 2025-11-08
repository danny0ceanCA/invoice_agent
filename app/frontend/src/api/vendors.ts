import { API_BASE, type ApiError } from "./auth";

export interface VendorProfile {
  id: number;
  company_name: string;
  contact_name: string | null;
  contact_email: string | null;
  phone_number: string | null;
  remit_to_address: string | null;
  is_profile_complete: boolean;
  district_company_name: string | null;
  is_district_linked: boolean;
}

export interface VendorProfilePayload {
  company_name: string;
  contact_name: string;
  contact_email: string;
  phone_number: string;
  remit_to_address: string;
  district_key: string | null;
}

async function vendorFetch<T>(
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

export async function fetchVendorProfile(
  accessToken: string,
): Promise<VendorProfile> {
  return vendorFetch<VendorProfile>("/vendors/me", accessToken);
}

export async function updateVendorProfile(
  accessToken: string,
  payload: VendorProfilePayload,
): Promise<VendorProfile> {
  return vendorFetch<VendorProfile>("/vendors/me", accessToken, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
