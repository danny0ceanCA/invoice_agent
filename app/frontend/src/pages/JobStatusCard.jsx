import useJobPolling from "../hooks/useJobPolling";

const statusColors = {
  queued: "bg-yellow-100 text-yellow-800",
  pending: "bg-yellow-100 text-yellow-800",
  started: "bg-blue-100 text-blue-800",
  running: "bg-blue-100 text-blue-800",
  done: "bg-green-100 text-green-800",
  success: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
  failure: "bg-red-100 text-red-800",
};

export default function JobStatusCard({ job }) {
  const { status, downloadUrl } = useJobPolling(
    job.id,
    4000,
    job.status ?? "queued",
    job.download_url ?? null
  );
  const badgeClass = statusColors[status] ?? "bg-slate-100 text-slate-700";

  return (
    <div className="p-4 border rounded-xl bg-white shadow-sm">
      <div className="flex justify-between items-center">
        <span className="font-medium">{job.filename}</span>
        <span className={`px-3 py-1 rounded-full text-sm capitalize ${badgeClass}`}>
          {status}
        </span>
      </div>
      {downloadUrl && (
        <a className="text-blue-600 mt-2 inline-block" href={downloadUrl}>
          Download Invoices
        </a>
      )}
    </div>
  );
}
