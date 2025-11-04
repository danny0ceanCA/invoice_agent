import { useCallback, useEffect, useMemo, useState } from "react";
import { uploadInvoice } from "../api/invoices";
import { listJobs } from "../api/jobs";
import JobStatusCard from "./JobStatusCard";

const vendorDirectory = [
  {
    id: 1,
    name: "Bright Futures Therapy",
    contact: "Amanda Lewis",
    email: "amanda@brightfutures.com",
    focus: "Speech therapy services across K-5 campuses",
    metrics: {
      campuses: 12,
      invoicesThisYear: 28,
      avgTurnaround: "3.2 days",
      outstanding: "$12,450",
    },
    highlights: [
      "Renewed district contract through FY25 with expanded coverage for three additional campuses.",
      "Providing bilingual clinicians for dual-language programs at Jefferson and Maple elementary schools.",
    ],
    invoiceSchedule: {
      2024: [
        { month: "April", total: "$12,050", count: 3, status: "Ready to Submit", dueDate: "May 5" },
        { month: "March", total: "$12,400", count: 3, status: "Processing", dueDate: "Apr 5" },
        { month: "February", total: "$11,980", count: 3, status: "Paid", dueDate: "Mar 5" },
        { month: "January", total: "$12,120", count: 3, status: "Paid", dueDate: "Feb 5" },
      ],
      2023: [
        { month: "December", total: "$11,760", count: 3, status: "Paid", dueDate: "Jan 5" },
        { month: "November", total: "$11,540", count: 3, status: "Paid", dueDate: "Dec 5" },
        { month: "October", total: "$10,870", count: 3, status: "Paid", dueDate: "Nov 5" },
      ],
    },
  },
  {
    id: 2,
    name: "North Shore Counseling",
    contact: "Marcus Hill",
    email: "marcus@northshorecounseling.org",
    focus: "Behavioral health support for middle school campuses",
    metrics: {
      campuses: 8,
      invoicesThisYear: 19,
      avgTurnaround: "2.6 days",
      outstanding: "$6,300",
    },
    highlights: [
      "Piloting a tiered intervention model with the student services department.",
      "Quarterly data reviews scheduled with campus directors for progress monitoring.",
    ],
    invoiceSchedule: {
      2024: [
        { month: "April", total: "$8,210", count: 2, status: "Draft", dueDate: "May 8" },
        { month: "March", total: "$8,560", count: 2, status: "Processing", dueDate: "Apr 8" },
        { month: "February", total: "$7,980", count: 2, status: "Paid", dueDate: "Mar 8" },
        { month: "January", total: "$7,640", count: 2, status: "Paid", dueDate: "Feb 8" },
      ],
      2023: [
        { month: "December", total: "$7,480", count: 2, status: "Paid", dueDate: "Jan 8" },
        { month: "November", total: "$7,330", count: 2, status: "Paid", dueDate: "Dec 8" },
      ],
    },
  },
  {
    id: 3,
    name: "STEM Sparks Enrichment",
    contact: "Priya Rao",
    email: "priya@stemsparks.io",
    focus: "After-school robotics and engineering clubs",
    metrics: {
      campuses: 5,
      invoicesThisYear: 14,
      avgTurnaround: "4.1 days",
      outstanding: "$3,890",
    },
    highlights: [
      "Launch of district-wide robotics showcase in partnership with the career pathways office.",
      "Recruiting additional mentors to support the north feeder pattern expansion.",
    ],
    invoiceSchedule: {
      2024: [
        { month: "April", total: "$6,240", count: 4, status: "Overdue", dueDate: "Apr 28" },
        { month: "March", total: "$6,080", count: 4, status: "Processing", dueDate: "Mar 28" },
        { month: "February", total: "$5,920", count: 4, status: "Paid", dueDate: "Feb 28" },
        { month: "January", total: "$5,870", count: 4, status: "Paid", dueDate: "Jan 28" },
      ],
      2023: [
        { month: "December", total: "$5,610", count: 4, status: "Paid", dueDate: "Dec 28" },
        { month: "November", total: "$5,420", count: 4, status: "Paid", dueDate: "Nov 28" },
        { month: "October", total: "$5,260", count: 4, status: "Paid", dueDate: "Oct 28" },
      ],
    },
  },
];

const sections = [
  { key: "overview", label: "Overview" },
  { key: "invoices", label: "Invoices" },
];

const statusStyles = {
  Paid: "bg-emerald-100 text-emerald-700",
  Processing: "bg-blue-100 text-blue-700",
  "Ready to Submit": "bg-amber-100 text-amber-700",
  Overdue: "bg-rose-100 text-rose-700",
  Draft: "bg-slate-100 text-slate-600",
};

const initialYear = Object.keys(vendorDirectory[0].invoiceSchedule)
  .sort((a, b) => Number(b) - Number(a))[0];

export default function VendorDashboard() {
  const [selectedVendorId, setSelectedVendorId] = useState(vendorDirectory[0].id);
  const [activeSection, setActiveSection] = useState("invoices");
  const [activeYear, setActiveYear] = useState(initialYear);
  const [jobs, setJobs] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  const selectedVendor = vendorDirectory.find((vendor) => vendor.id === selectedVendorId) ?? vendorDirectory[0];

  const invoiceYears = useMemo(() => {
    if (!selectedVendor) return [];
    return Object.keys(selectedVendor.invoiceSchedule).sort((a, b) => Number(b) - Number(a));
  }, [selectedVendor]);

  useEffect(() => {
    if (invoiceYears.length === 0) return;
    setActiveYear((current) => (invoiceYears.includes(current) ? current : invoiceYears[0]));
  }, [invoiceYears]);

  const fetchJobs = useCallback(async () => {
    setError(null);
    try {
      const recentJobs = await listJobs();
      setJobs(recentJobs);
    } catch (err) {
      setError("Unable to load jobs");
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const timer = setInterval(fetchJobs, 5000);
    return () => clearInterval(timer);
  }, [fetchJobs]);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const payload = {
        vendor_id: selectedVendor.id,
        invoice_date: new Date().toISOString().split("T")[0],
        service_month: new Date().toLocaleString("default", { month: "long", year: "numeric" }),
        invoice_code: `INV-${Date.now()}`,
      };
      await uploadInvoice(file, payload);
      await fetchJobs();
    } catch (err) {
      setError("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  const monthEntries = selectedVendor?.invoiceSchedule?.[activeYear] ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-emerald-600">
            Vendor Workspace
          </p>
          <h1 className="text-2xl font-bold">Manage partnerships and billing in one place</h1>
          <p className="mt-1 text-sm text-slate-500">
            Quickly review vendor activity, launch invoice generation, and monitor processing updates.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Vendors</h2>
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
              {vendorDirectory.length} total
            </span>
          </div>
          <div className="mt-4 space-y-2">
            {vendorDirectory.map((vendor) => {
              const isActive = vendor.id === selectedVendorId;
              return (
                <button
                  key={vendor.id}
                  type="button"
                  onClick={() => {
                    setSelectedVendorId(vendor.id);
                  }}
                  className={`w-full rounded-lg border px-4 py-3 text-left transition ${
                    isActive
                      ? "border-emerald-500 bg-white shadow-sm"
                      : "border-transparent bg-white/70 hover:border-slate-200 hover:bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{vendor.name}</p>
                      <p className="text-xs text-slate-500">{vendor.focus}</p>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      {vendor.metrics.invoicesThisYear} invoices
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <span>{vendor.contact}</span>
                    <span className="font-medium text-emerald-600">{vendor.metrics.outstanding} due</span>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="space-y-6">
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">{selectedVendor.name}</h2>
                <p className="text-sm text-slate-500">{selectedVendor.focus}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-sm text-slate-500">
                <span className="rounded-full border border-slate-200 px-3 py-1">
                  {selectedVendor.contact}
                </span>
                <span className="rounded-full border border-slate-200 px-3 py-1">
                  {selectedVendor.email}
                </span>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard label="Campuses served" value={selectedVendor.metrics.campuses} />
              <MetricCard label="Invoices this year" value={selectedVendor.metrics.invoicesThisYear} />
              <MetricCard label="Avg. processing time" value={selectedVendor.metrics.avgTurnaround} />
              <MetricCard label="Outstanding balance" value={selectedVendor.metrics.outstanding} emphasize />
            </div>

            <div className="flex items-center gap-2 border-b border-slate-200 pt-2">
              {sections.map((section) => (
                <button
                  key={section.key}
                  type="button"
                  onClick={() => setActiveSection(section.key)}
                  className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                    activeSection === section.key
                      ? "bg-emerald-500 text-white shadow"
                      : "text-slate-500 hover:bg-slate-100"
                  }`}
                >
                  {section.label}
                </button>
              ))}
            </div>

            {activeSection === "overview" ? (
              <div className="space-y-4">
                <p className="text-sm text-slate-600">
                  Stay aligned on partnership priorities, staffing, and contract milestones before diving into billing
                  actions.
                </p>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-3 rounded-lg border border-slate-200 p-4">
                    <h3 className="text-sm font-semibold text-slate-700">Current focus areas</h3>
                    <ul className="space-y-2 text-sm text-slate-600">
                      {selectedVendor.highlights.map((item, index) => (
                        <li key={item} className="flex items-start gap-2">
                          <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                    <h3 className="text-sm font-semibold text-slate-700">Next touchpoint</h3>
                    <p className="mt-2">
                      Schedule a service review with {selectedVendor.contact.split(" ")[0]} to confirm staffing plans for
                      summer programming and fall ramp-up.
                    </p>
                    <p className="mt-3 text-xs text-slate-500">
                      Tip: Log meeting notes directly after the conversation so finance, SPED, and campus operations stay
                      aligned.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="grid gap-4 lg:grid-cols-[140px_1fr]">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Years</h3>
                    <div className="mt-3 space-y-2">
                      {invoiceYears.map((year) => (
                        <button
                          key={year}
                          type="button"
                          onClick={() => setActiveYear(year)}
                          className={`w-full rounded-md px-3 py-2 text-left text-sm font-medium transition ${
                            activeYear === year
                              ? "bg-emerald-500 text-white shadow"
                              : "text-slate-600 hover:bg-white"
                          }`}
                        >
                          {year}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <h3 className="text-lg font-semibold text-slate-900">{activeYear} invoice cadence</h3>
                        <p className="text-sm text-slate-500">
                          Track monthly billing packages and launch new invoice processing runs without leaving this view.
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                      {monthEntries.map((entry) => (
                        <div key={`${entry.month}-${entry.status}`} className="rounded-lg border border-slate-200 p-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <p className="text-xs uppercase tracking-wide text-slate-500">{entry.month}</p>
                              <p className="mt-1 text-lg font-semibold text-slate-900">{entry.total}</p>
                            </div>
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                statusStyles[entry.status] ?? "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {entry.status}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-slate-500">
                            {entry.count} invoice package{entry.count > 1 ? "s" : ""} • Due {entry.dueDate}
                          </p>
                          <button
                            type="button"
                            className="mt-4 w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-emerald-500 hover:text-emerald-600"
                          >
                            Open invoice folder
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-dashed border-emerald-300 bg-emerald-50/70 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-emerald-800">Generate a new invoice package</h3>
                      <p className="text-sm text-emerald-700">
                        Upload the vendor's raw timesheet to trigger automated parsing and reconciliation.
                      </p>
                    </div>
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white shadow transition hover:bg-emerald-600">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        onChange={handleUpload}
                        disabled={isUploading}
                        className="sr-only"
                      />
                      {isUploading ? "Uploading..." : "Upload timesheet"}
                    </label>
                  </div>
                  {error && <p className="mt-2 text-sm text-emerald-900">{error}</p>}
                </div>

                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-700">Processing updates</h3>
                  <p className="text-sm text-slate-500">
                    Jobs refresh automatically every few seconds while invoice generation runs in the background.
                  </p>
                  <div className="space-y-3">
                    {jobs.length === 0 ? (
                      <p className="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-500">
                        No active invoice jobs yet. Start a run to see progress here.
                      </p>
                    ) : (
                      jobs.map((job) => <JobStatusCard key={job.id} job={job} />)
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function MetricCard({ label, value, emphasize = false }) {
  return (
    <div
      className={`rounded-lg border border-slate-200 bg-white p-4 text-sm ${
        emphasize ? "shadow-sm ring-1 ring-emerald-100" : ""
      }`}
    >
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
