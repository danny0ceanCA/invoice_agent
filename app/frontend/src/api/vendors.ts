import { API_BASE, type ApiError } from "./auth";
import type { PostalAddress } from "./common";

export interface VendorProfile {
  id: number;
  company_name: string;
  contact_name: string | null;
  contact_email: string | null;
  phone_number: string | null;
  remit_to_address: PostalAddress | null;
  is_profile_complete: boolean;
  district_company_name: string | null;
  is_district_linked: boolean;
}

export interface VendorProfilePayload {
  company_name: string;
  contact_name: string;
  contact_email: string;
  phone_number: string;
  remit_to_address: PostalAddress;
  districtKey?: string;
}

export interface VendorDistrictLink {
  district_id: number | null;
  district_name: string | null;
  district_key: string | null;
  is_linked: boolean;
}

export interface VendorDistrictKeyPayload {
  district_key: string;
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

export async function fetchVendorDistrictLink(
  accessToken: string,
): Promise<VendorDistrictLink> {
  return vendorFetch<VendorDistrictLink>("/vendors/me/district-key", accessToken);
}

export async function registerVendorDistrictKey(
  accessToken: string,
  payload: VendorDistrictKeyPayload,
): Promise<VendorDistrictLink> {
  return vendorFetch<VendorDistrictLink>("/vendors/me/district-key", accessToken, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
