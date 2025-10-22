import axios from "axios";

export interface Job {
  id: number;
  vendor_id: number;
  invoice_id: number | null;
  filename: string;
  status: "queued" | "running" | "completed" | "skipped" | "error";
  message: string | null;
  created_at: string;
  download_url: string | null;
}

export async function listJobs(): Promise<Job[]> {
  const res = await axios.get<Job[]>("/api/jobs");
  return res.data;
}
