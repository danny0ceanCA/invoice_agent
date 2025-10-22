import { useEffect, useState } from "react";
import { uploadInvoice } from "../api/invoices";
import { listJobs } from "../api/jobs";
import JobStatusCard from "./JobStatusCard";

export default function VendorDashboard() {
  const [jobs, setJobs] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchJobs() {
      try {
        const recentJobs = await listJobs();
        setJobs(recentJobs);
      } catch (err) {
        setError("Unable to load jobs");
      }
    }
    fetchJobs();
  }, []);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const payload = {
        vendor_id: 1,
        invoice_date: new Date().toISOString().split("T")[0],
        service_month: new Date().toLocaleString("default", { month: "long", year: "numeric" }),
        invoice_code: `INV-${Date.now()}`,
      };
      const response = await uploadInvoice(file, payload);
      setJobs((previous) => [
        { id: response.job_id, filename: file.name, status: "queued" },
        ...previous,
      ]);
    } catch (err) {
      setError("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Upload Timesheets</h1>
      <p className="text-slate-600 mb-4">
        Upload a raw Excel timesheet to kick off automated invoice generation. The platform
        processes the file asynchronously and streams status updates below.
      </p>
      <input type="file" accept=".xlsx,.xls" onChange={handleUpload} disabled={isUploading} />
      {error && <p className="text-red-600 mt-2 text-sm">{error}</p>}
      <div className="mt-6 space-y-3">
        {jobs.map((job) => (
          <JobStatusCard key={job.id} job={job} />
        ))}
      </div>
    </div>
  );
}
