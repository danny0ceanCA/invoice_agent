const DEFAULT_API_BASE_URL = "/api";

function resolveApiBase(rawBase?: string): string {
  if (!rawBase) {
    return DEFAULT_API_BASE_URL;
  }

  const trimmed = rawBase.trim();
  if (!trimmed) {
    return DEFAULT_API_BASE_URL;
  }

  try {
    const url = new URL(trimmed);
    if (url.pathname === "" || url.pathname === "/") {
      url.pathname = "/api";
    }
    return url.toString().replace(/\/$/, "");
  } catch (error) {
    if (trimmed.startsWith("/")) {
      const normalizedPath = trimmed === "/" ? "/api" : trimmed;
      return normalizedPath.replace(/\/$/, "");
    }

    console.warn(
      `Invalid VITE_API_BASE_URL "${trimmed}". Falling back to ${DEFAULT_API_BASE_URL}.`,
      error,
    );
    return DEFAULT_API_BASE_URL;
  }
}

export const API_BASE = resolveApiBase(import.meta.env.VITE_API_BASE_URL);

export type UserRole = "vendor" | "district" | "admin";
export type RoleSelectionOption = Exclude<UserRole, "admin">;

export interface DistrictMembershipEntry {
  district_id: number;
  company_name: string;
  district_key: string;
  is_active: boolean;
}

export interface ApiError extends Error {
  status?: number;
  statusText?: string;
}

export interface CurrentUserResponse {
  id: number;
  email: string;
  name: string;
  role: UserRole | null;
  vendor_id: number | null;
  district_id: number | null;
  active_district_id: number | null;
  district_memberships: DistrictMembershipEntry[];
  auth0_sub: string | null;
  needs_role_selection: boolean;
}

async function apiFetch<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
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

export async function fetchCurrentUser(accessToken: string): Promise<CurrentUserResponse> {
  return apiFetch<CurrentUserResponse>("/auth/me", accessToken);
}

export async function selectUserRole(
  accessToken: string,
  role: RoleSelectionOption,
): Promise<CurrentUserResponse> {
  // The onboarding endpoint lives under the users namespace on the backend.
  // Using the auth prefix results in a 404, leaving new accounts stuck on the
  // role selection screen.
  return apiFetch<CurrentUserResponse>("/users/set-role", accessToken, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}
