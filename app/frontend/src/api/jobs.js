const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function listJobs(accessToken) {
  if (!accessToken) {
    throw new Error("Missing access token");
  }

  const response = await fetch(`${API_BASE}/api/jobs`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }

  return response.json();
}
