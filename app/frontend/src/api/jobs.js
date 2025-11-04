import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE,
  headers: { "X-User-Id": "1" },
});

export async function listJobs() {
  const response = await client.get("/api/jobs");
  return response.data;
}
