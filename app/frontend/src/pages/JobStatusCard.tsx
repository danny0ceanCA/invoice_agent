import type { Job } from "../api/jobs";

interface JobStatusCardProps {
  job: Job;
}

const STATUS_STYLE: Record<Job["status"], string> = {
  queued: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  skipped: "bg-gray-200 text-gray-700",
  error: "bg-red-100 text-red-800",
};

export default function JobStatusCard({ job }: JobStatusCardProps) {
  const color = STATUS_STYLE[job.status];

  const label =
    job.status === "skipped"
      ? "Skipped (Duplicate)"
      : job.status.charAt(0).toUpperCase() + job.status.slice(1);

  return (
    <div className="p-4 border rounded-xl shadow-sm mb-3">
      <div className="flex justify-between items-center">
        <span className="font-medium">{job.filename}</span>
        <span className={`px-3 py-1 rounded-full text-sm ${color}`}>{label}</span>
      </div>
      {job.message && <p className="text-sm mt-2 text-gray-600">{job.message}</p>}
      {job.status === "completed" && job.download_url && (
        <a
          href={job.download_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-blue-600 hover:underline"
        >
          Download Invoice
        </a>
      )}
    </div>
  );
}
