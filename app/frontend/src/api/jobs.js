const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function getJobStatus(id) {
  const response = await fetch(`${API_BASE}/api/jobs/${id}`, {
    headers: { "X-User-Id": "1" },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch job ${id}`);
  }
  return response.json();
}

export async function listJobs() {
  const response = await fetch(`${API_BASE}/api/jobs`, {
    headers: { "X-User-Id": "1" },
  });
  if (!response.ok) {
    throw new Error("Failed to fetch jobs");
  }
  return response.json();
}
