import { API_BASE } from "./auth";

export async function listJobs(accessToken) {
  if (!accessToken) {
    throw new Error("Missing access token");
  }

  const response = await fetch(`${API_BASE}/jobs`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }

  return response.json();
}
