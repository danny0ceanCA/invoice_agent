import { useEffect, useState, type ChangeEvent } from "react";

import { listJobs, type Job } from "../api/jobs";
import { uploadInvoice } from "../api/invoices";
import JobStatusCard from "./JobStatusCard";

export default function VendorDashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchJobs() {
      try {
        const data = await listJobs();
        setJobs(data);
      } catch (err) {
        console.error(err);
        setError("Unable to load jobs. Please try again later.");
      }
    }

    fetchJobs();
  }, []);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const meta = {
        vendor_id: 1,
        invoice_date: new Date().toISOString().split("T")[0],
        service_month: new Intl.DateTimeFormat("en-US", {
          month: "long",
          year: "numeric",
        }).format(new Date()),
      };

      await uploadInvoice(file, meta);
      const updated = await listJobs();
      setJobs(updated);
    } catch (err) {
      console.error(err);
      setError("Upload failed. Please verify the file and try again.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">Upload Timesheets</h1>
        <p className="text-sm text-gray-600 mb-4">
          Upload a CSV export of your timesheets to generate invoices automatically.
        </p>
        <input
          type="file"
          accept=".csv"
          onChange={handleUpload}
          disabled={isUploading}
          className="block"
        />
        {isUploading && <p className="text-sm text-blue-600 mt-2">Processing upload…</p>}
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      <div>
        <h2 className="text-xl font-semibold mb-3">Recent Jobs</h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-gray-500">No jobs yet. Upload a file to get started.</p>
        ) : (
          jobs.map((job) => <JobStatusCard key={job.id} job={job} />)
        )}
      </div>
    </div>
  );
}
