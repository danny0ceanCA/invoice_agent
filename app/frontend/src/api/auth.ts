const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type UserRole = "vendor" | "district" | "admin";
export type RoleSelectionOption = Exclude<UserRole, "admin">;

export interface CurrentUserResponse {
  id: number;
  email: string;
  name: string;
  role: UserRole | null;
  vendor_id: number | null;
  auth0_sub: string | null;
  needs_role_selection: boolean;
}

async function apiFetch<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
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
    throw new Error(message || `Request to ${path} failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchCurrentUser(accessToken: string): Promise<CurrentUserResponse> {
  return apiFetch<CurrentUserResponse>("/api/auth/me", accessToken);
}

export async function selectUserRole(
  accessToken: string,
  role: RoleSelectionOption,
): Promise<CurrentUserResponse> {
  return apiFetch<CurrentUserResponse>("/api/users/set-role", accessToken, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}
