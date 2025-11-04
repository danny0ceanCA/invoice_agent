import { useCallback, useEffect, useMemo, useState } from "react";
import { uploadInvoice } from "../api/invoices";
import { listJobs } from "../api/jobs";
import { fetchVendorDashboard } from "../api/vendors";
import JobStatusCard from "./JobStatusCard";

const REQUIRED_COLUMNS = [
  "Client",
  "Schedule Date",
  "Hours",
  "Employee",
  "Service Code",
];

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function formatCurrency(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "$0.00";
  }
  return currencyFormatter.format(value);
}

function formatHours(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "0.00 hrs";
  }
  return `${value.toFixed(2)} hrs`;
}

function formatDate(value) {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function VendorDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [file, setFile] = useState(null);
  const [fileKey, setFileKey] = useState(() => Date.now());
  const [invoiceDate, setInvoiceDate] = useState(() => {
    const today = new Date();
    return today.toISOString().slice(0, 10);
  });
  const [serviceMonth, setServiceMonth] = useState(() => {
    const today = new Date();
    return today.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  });
  const [invoiceCode, setInvoiceCode] = useState("");
  const [alert, setAlert] = useState(null);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const vendorId = dashboard?.vendor?.id ?? null;

  const loadDashboard = useCallback(async () => {
    setLoadingDashboard(true);
    try {
      const data = await fetchVendorDashboard();
      setDashboard(data);
    } catch (error) {
      console.error("Failed to load vendor dashboard", error);
      setAlert({ type: "error", message: "Unable to load vendor data. Please refresh." });
    } finally {
      setLoadingDashboard(false);
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to load jobs", error);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
    loadJobs();
  }, [loadDashboard, loadJobs]);

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!file) {
        setAlert({ type: "error", message: "Choose a .xlsx timesheet before uploading." });
        return;
      }
      if (!vendorId) {
        setAlert({ type: "error", message: "Vendor profile not loaded yet." });
        return;
      }

      setSubmitting(true);
      setAlert({ type: "info", message: "Uploading timesheet and starting invoice generation…" });
      try {
        const response = await uploadInvoice(file, {
          vendor_id: vendorId,
          invoice_date: invoiceDate,
          service_month: serviceMonth,
          invoice_code: invoiceCode.trim() || undefined,
        });
        setAlert({
          type: "success",
          message: `Upload received. Job ${response.job_id} is queued for processing.`,
        });
        setFile(null);
        setFileKey(Date.now());
        setInvoiceCode("");
        await loadJobs();
      } catch (error) {
        console.error("Timesheet upload failed", error);
        setAlert({ type: "error", message: "Upload failed. Please verify the file and try again." });
      } finally {
        setSubmitting(false);
      }
    },
    [file, vendorId, invoiceDate, serviceMonth, invoiceCode, loadJobs]
  );

  const summaryCards = useMemo(() => {
    if (!dashboard?.summary) {
      return [];
    }
    const summary = dashboard.summary;
    return [
      {
        label: "Students Served",
        value: summary.students_served ?? 0,
      },
      {
        label: "Total Hours",
        value: formatHours(summary.total_hours ?? 0),
      },
      {
        label: "Total Cost",
        value: formatCurrency(summary.total_cost ?? 0),
      },
      {
        label: "Invoices Generated",
        value: summary.invoice_count ?? 0,
      },
    ];
  }, [dashboard]);

  const latestInvoiceDate = dashboard?.summary?.latest_invoice_date
    ? formatDate(dashboard.summary.latest_invoice_date)
    : null;

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Vendor Portal</h2>
            <p className="text-sm text-slate-600">
              Upload monthly timesheets and monitor the automation that prepares student invoices.
            </p>
            {latestInvoiceDate && (
              <p className="text-xs text-slate-500">Last invoice generated on {latestInvoiceDate}.</p>
            )}
          </div>
          <button
            type="button"
            onClick={loadDashboard}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-100"
            disabled={loadingDashboard}
          >
            {loadingDashboard ? "Refreshing…" : "Refresh data"}
          </button>
        </div>
        {alert && (
          <div
            className={`rounded-md border px-4 py-3 text-sm ${
              alert.type === "error"
                ? "border-red-200 bg-red-50 text-red-700"
                : alert.type === "success"
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-slate-200 bg-slate-50 text-slate-700"
            }`}
          >
            {alert.message}
          </div>
        )}
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summaryCards.length ? (
          summaryCards.map((card) => (
            <div key={card.label} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs uppercase tracking-wide text-slate-500">{card.label}</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{card.value}</p>
            </div>
          ))
        ) : (
          <div className="sm:col-span-2 lg:col-span-4 rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
            No invoices have been generated yet. Upload a timesheet to create your first batch.
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Upload monthly timesheet</h3>
          <p className="text-sm text-slate-600">
            Use the export from your staffing system. The spreadsheet must include the following columns:
          </p>
          <ul className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
            {REQUIRED_COLUMNS.map((column) => (
              <li key={column} className="rounded-full border border-slate-300 px-3 py-1">
                {column}
              </li>
            ))}
          </ul>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col text-sm font-medium text-slate-700">
              Invoice date
              <input
                type="date"
                value={invoiceDate}
                onChange={(event) => setInvoiceDate(event.target.value)}
                className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
                required
              />
            </label>
            <label className="flex flex-col text-sm font-medium text-slate-700">
              Month of service
              <input
                type="text"
                value={serviceMonth}
                onChange={(event) => setServiceMonth(event.target.value)}
                placeholder="e.g. September 2024"
                className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
                required
              />
            </label>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col text-sm font-medium text-slate-700">
              Optional invoice code
              <input
                type="text"
                value={invoiceCode}
                onChange={(event) => setInvoiceCode(event.target.value)}
                placeholder="e.g. HWH"
                className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
              />
            </label>
            <label className="flex flex-col text-sm font-medium text-slate-700">
              Upload Excel timesheet (.xlsx)
              <input
                key={fileKey}
                type="file"
                accept=".xlsx,.xls"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
                required
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {submitting ? "Uploading…" : "Upload timesheet"}
            </button>
            <span className="text-xs text-slate-500">
              The automation will generate student invoices, PDFs, and a ZIP archive in the background.
            </span>
          </div>
        </form>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Recent jobs</h3>
          <button
            type="button"
            onClick={loadJobs}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-100"
          >
            Refresh queue
          </button>
        </div>
        {jobs.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {jobs.map((job) => (
              <JobStatusCard key={job.id} job={job} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-600">
            No jobs yet. Upload a timesheet to see processing status and download links.
          </p>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Generated invoices</h3>
          <p className="text-xs text-slate-500">Sorted by most recent service month.</p>
        </div>
        {dashboard?.invoices?.length ? (
          <div className="space-y-4">
            {dashboard.invoices.map((invoice) => (
              <article key={invoice.id} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h4 className="text-base font-semibold text-slate-900">{invoice.student_name}</h4>
                    <p className="text-sm text-slate-600">
                      {invoice.service_month} · Invoice {invoice.invoice_number}
                    </p>
                    <p className="text-xs text-slate-500">
                      Created {formatDate(invoice.invoice_date)} · Status {invoice.status}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold text-slate-900">{formatCurrency(invoice.total_cost)}</p>
                    <p className="text-xs text-slate-600">{formatHours(invoice.total_hours)}</p>
                    {invoice.pdf_url && (
                      <a
                        href={invoice.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-block text-sm font-medium text-blue-600 hover:underline"
                      >
                        Download PDF
                      </a>
                    )}
                  </div>
                </div>
                {invoice.line_items?.length ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                        <tr>
                          <th className="px-3 py-2">Service date</th>
                          <th className="px-3 py-2">Clinician</th>
                          <th className="px-3 py-2">Service code</th>
                          <th className="px-3 py-2 text-right">Hours</th>
                          <th className="px-3 py-2 text-right">Rate</th>
                          <th className="px-3 py-2 text-right">Cost</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {invoice.line_items.map((item) => (
                          <tr key={item.id} className="text-slate-700">
                            <td className="px-3 py-2">{formatDate(item.service_date)}</td>
                            <td className="px-3 py-2">{item.clinician}</td>
                            <td className="px-3 py-2">{item.service_code}</td>
                            <td className="px-3 py-2 text-right">{formatHours(item.hours)}</td>
                            <td className="px-3 py-2 text-right">{formatCurrency(item.rate)}</td>
                            <td className="px-3 py-2 text-right">{formatCurrency(item.cost)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">No line items were stored for this invoice.</p>
                )}
              </article>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-600">
            Once processing completes you will see student-level invoices here with PDF download links and detailed line
            items.
          </p>
        )}
      </section>
    </div>
  );
}
