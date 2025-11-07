import { API_BASE } from "./auth";

async function request(path, token, init = {}) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_BASE}${normalizedPath}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request to ${path} failed with status ${response.status}`);
  }

  return response.json();
}

export async function listUsers(token) {
  return request("/admin/users", token);
}

export async function listPendingUsers(token) {
  return request("/admin/users/pending", token);
}

export async function approveUser(id, token) {
  const response = await request(`/admin/users/${id}/approve`, token, { method: "PATCH" });

  if (response && response.user) {
    return {
      ...response.user,
      is_approved:
        response.user.approved ?? response.user.is_approved ?? false,
    };
  }

  return response;
}

export async function updateUserRole(id, role, token) {
  return request(`/admin/users/${id}/role`, token, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export async function deactivateUser(id, token) {
  return request(`/admin/users/${id}/deactivate`, token, { method: "PATCH" });
}

