export default function JobStatusCard({ job }) {
  const status = job.status ?? "queued";
  const colors = {
    queued: "bg-yellow-100 text-yellow-800",
    running: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    skipped: "bg-gray-200 text-gray-700",
    error: "bg-red-100 text-red-800",
  };
  const badgeClass = colors[status] ?? "bg-slate-100 text-slate-700";
  const label =
    status === "skipped"
      ? "Skipped (Duplicate)"
      : status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm">
      <div className="flex justify-between items-center">
        <span className="font-medium">{job.filename}</span>
        <span className={`px-3 py-1 rounded-full text-sm ${badgeClass}`}>
          {label}
        </span>
      </div>
      {job.message && <p className="text-sm mt-2 text-gray-600">{job.message}</p>}
      {status === "completed" && job.download_url && (
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
