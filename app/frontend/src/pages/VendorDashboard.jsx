import { useCallback, useEffect, useMemo, useState } from "react";
import { uploadInvoice } from "../api/invoices";
import { listJobs } from "../api/jobs";
import JobStatusCard from "./JobStatusCard";

const vendorProfile = {
  name: "Harbor Education Services",
  tagline: "Partnering with districts to deliver bilingual speech therapy at scale.",
  manager: {
    name: "Alana Ruiz",
    title: "Account Director",
    email: "alana@harboredu.com",
    phone: "(555) 214-0183",
  },
  serviceSnapshot: [
    {
      id: "slp",
      name: "Speech Language Pathology",
      students: 18,
      trend: "+6.4% YoY",
      amount: "$48,320",
    },
    {
      id: "rn",
      name: "Registered Nursing",
      students: 12,
      trend: "+3.1% YoY",
      amount: "$36,480",
    },
    {
      id: "cota",
      name: "Certified OTA",
      students: 7,
      trend: "Stable",
      amount: "$21,600",
    },
  ],
  invoices: {
    2024: [
      {
        month: "April",
        total: "$19,120",
        status: "Draft",
        processedOn: "Upload pending",
        pdfUrl: null,
        timesheetCsvUrl: null,
        notes: "Timesheet upload in progress.",
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,120" },
          { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$3,055" },
          { id: "sophia-cabrera", name: "Sophia Cabrera", service: "SLP", amount: "$2,985" },
        ],
      },
      {
        month: "March",
        total: "$19,120",
        status: "In Review",
        processedOn: "Apr 8, 2024",
        pdfUrl: "/invoices/harbor-education/march-2024.pdf",
        timesheetCsvUrl: "/timesheets/harbor-education/march-2024.csv",
        notes: "Awaiting district approval on two student line items.",
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,105" },
          { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$3,020" },
          { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,180" },
          { id: "riley-watts", name: "Riley Watts", service: "SLP", amount: "$2,920" },
        ],
      },
      {
        month: "February",
        total: "$18,240",
        status: "Approved",
        processedOn: "Mar 4, 2024",
        pdfUrl: "/invoices/harbor-education/february-2024.pdf",
        timesheetCsvUrl: "/timesheets/harbor-education/february-2024.csv",
        notes: "No action needed.",
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,041" },
          { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$2,996" },
          { id: "sophia-cabrera", name: "Sophia Cabrera", service: "SLP", amount: "$3,155" },
          { id: "leo-kim", name: "Leo Kim", service: "SLP", amount: "$2,890" },
        ],
      },
      {
        month: "January",
        total: "$18,240",
        status: "Approved",
        processedOn: "Feb 2, 2024",
        pdfUrl: "/invoices/harbor-education/january-2024.pdf",
        timesheetCsvUrl: "/timesheets/harbor-education/january-2024.csv",
        notes: "Invoice paid on Feb 15.",
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,041" },
          { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$2,996" },
          { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,210" },
          { id: "riley-watts", name: "Riley Watts", service: "SLP", amount: "$2,870" },
        ],
      },
    ],
    2023: [
      {
        month: "December",
        total: "$18,240",
        status: "Approved",
        processedOn: "Jan 5, 2024",
        pdfUrl: "/invoices/harbor-education/december-2023.pdf",
        timesheetCsvUrl: "/timesheets/harbor-education/december-2023.csv",
        notes: "Archived in district portal.",
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,005" },
          { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$2,960" },
          { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,120" },
        ],
      },
      {
        month: "November",
        total: "$17,880",
        status: "Approved",
        processedOn: "Dec 7, 2023",
        pdfUrl: "/invoices/harbor-education/november-2023.pdf",
        timesheetCsvUrl: "/timesheets/harbor-education/november-2023.csv",
        notes: "Payment received Dec 20.",
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$2,940" },
          { id: "riley-watts", name: "Riley Watts", service: "SLP", amount: "$3,045" },
        ],
      },
      {
        month: "October",
        total: "$17,880",
        status: "Approved",
        processedOn: "Nov 6, 2023",
        pdfUrl: "/invoices/harbor-education/october-2023.pdf",
        timesheetCsvUrl: "/timesheets/harbor-education/october-2023.csv",
        notes: "Closed", 
        students: [
          { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$2,940" },
          { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,115" },
        ],
      },
    ],
  },
};

export default function VendorDashboard() {
  const [jobs, setJobs] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const fiscalMonthOrder = useMemo(
    () => [
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
    ],
    []
  );
  const invoiceYears = useMemo(
    () => Object.keys(vendorProfile.invoices).sort((a, b) => Number(b) - Number(a)),
    []
  );
  const [selectedYear, setSelectedYear] = useState(invoiceYears[0]);
  const yearInvoices = useMemo(
    () =>
      [...(vendorProfile.invoices[selectedYear] ?? [])].sort((a, b) => {
        const monthIndexA = fiscalMonthOrder.indexOf(a.month);
        const monthIndexB = fiscalMonthOrder.indexOf(b.month);
        const safeIndexA = monthIndexA === -1 ? Number.MAX_SAFE_INTEGER : monthIndexA;
        const safeIndexB = monthIndexB === -1 ? Number.MAX_SAFE_INTEGER : monthIndexB;
        return safeIndexA - safeIndexB;
      }),
    [selectedYear, fiscalMonthOrder]
  );
  const [selectedMonth, setSelectedMonth] = useState(yearInvoices[0]?.month ?? null);

  useEffect(() => {
    setSelectedMonth((prev) => {
      if (yearInvoices.find((invoice) => invoice.month === prev)) {
        return prev;
      }
      return yearInvoices[0]?.month ?? null;
    });
  }, [yearInvoices]);

  const selectedInvoice = useMemo(
    () => yearInvoices.find((invoice) => invoice.month === selectedMonth) ?? null,
    [yearInvoices, selectedMonth]
  );

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
        vendor_id: 1,
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

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <header className="mx-auto max-w-6xl">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-500">Vendor Portal</p>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">{vendorProfile.name}</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">{vendorProfile.tagline}</p>
          </div>
        </div>
      </header>

      <div className="mx-auto mt-8 grid max-w-6xl gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Account Team</h2>
            <p className="mt-2 text-sm text-slate-600">
              {vendorProfile.manager.name} · {vendorProfile.manager.title}
            </p>
            <dl className="mt-4 space-y-2 text-sm text-slate-600">
              <div className="flex items-center justify-between">
                <dt className="text-slate-500">Email</dt>
                <dd>
                  <a
                    href={`mailto:${vendorProfile.manager.email}`}
                    className="font-medium text-amber-600 hover:text-amber-700"
                  >
                    {vendorProfile.manager.email}
                  </a>
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500">Phone</dt>
                <dd className="font-medium text-slate-900">{vendorProfile.manager.phone}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Service Snapshot</h2>
            <ul className="mt-4 space-y-4">
              {vendorProfile.serviceSnapshot.map((service) => (
                <li key={service.id} className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{service.name}</p>
                    <p className="text-xs text-slate-500">{service.students} students supported</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-slate-900">{service.amount}</p>
                    <p className="text-xs text-emerald-600">{service.trend}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Upcoming actions and helpful resources sections removed as per request */}
        </aside>

        <main className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Upload Timesheets</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Upload a raw Excel timesheet to kick off automated invoice generation. Status updates
                  appear below within a few seconds of submission.
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-amber-400 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 shadow-sm transition hover:border-amber-500 hover:bg-amber-100">
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleUpload}
                  disabled={isUploading}
                  className="sr-only"
                />
                {isUploading ? "Uploading…" : "Select File"}
              </label>
            </div>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

            <div className="mt-6 space-y-3">
              {jobs.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No recent uploads. Submit your latest timesheet to generate a draft invoice.
                </p>
              ) : (
                jobs.map((job) => <JobStatusCard key={job.id} job={job} />)
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Invoice History</h2>
              </div>
              <div className="flex items-center gap-2">
                {invoiceYears.map((year) => (
                  <button
                    key={year}
                    onClick={() => setSelectedYear(year)}
                    type="button"
                    className={`rounded-full px-3 py-1 text-sm font-medium transition ${
                      year === selectedYear
                        ? "bg-amber-500 text-white shadow"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {year}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-[220px_1fr]">
              <nav
                className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1"
                aria-label="Select invoice month"
              >
                {yearInvoices.map((invoice) => (
                  <button
                    key={`${selectedYear}-${invoice.month}`}
                    type="button"
                    onClick={() => setSelectedMonth(invoice.month)}
                    className={`group flex w-full items-center justify-between rounded-xl border px-4 py-3 text-sm font-semibold uppercase tracking-wide transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500 ${
                      invoice.month === selectedMonth
                        ? "border-amber-400 bg-amber-50 text-amber-700 shadow-sm"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    <span>{invoice.month}</span>
                    <svg
                      viewBox="0 0 20 20"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      className={`h-4 w-4 transition ${
                        invoice.month === selectedMonth
                          ? "text-amber-600"
                          : "text-slate-300 group-hover:text-slate-400"
                      }`}
                    >
                      <path
                        d="M7.5 5l5 5-5 5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                ))}
              </nav>

              {selectedInvoice ? (
                <div className="space-y-6">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-slate-500">{selectedMonth}</p>
                        <h3 className="text-2xl font-bold text-slate-900">{selectedInvoice.total}</h3>
                        <p className="mt-2 text-sm text-slate-600">Processed on {selectedInvoice.processedOn}</p>
                      </div>
                      <span className="inline-flex items-center rounded-full bg-emerald-100 px-4 py-1 text-sm font-medium text-emerald-700">
                        {selectedInvoice.status}
                      </span>
                    </div>
                    <p className="mt-4 text-sm text-slate-600">{selectedInvoice.notes}</p>
                    <div className="mt-5 flex flex-wrap gap-3">
                      {selectedInvoice.pdfUrl ? (
                        <a
                          href={selectedInvoice.pdfUrl}
                          className="inline-flex items-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400"
                        >
                          Download PDF
                        </a>
                      ) : null}
                      {selectedInvoice.timesheetCsvUrl ? (
                        <a
                          href={selectedInvoice.timesheetCsvUrl}
                          className="inline-flex items-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400"
                        >
                          Download Timesheet CSV
                        </a>
                      ) : null}
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-2xl border border-slate-200">
                    <table className="min-w-full divide-y divide-slate-200">
                      <thead className="bg-slate-100">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                            Student
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                            Service
                          </th>
                          <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wide text-slate-600">
                            Amount
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 bg-white">
                        {selectedInvoice.students.map((student) => (
                          <tr key={student.id}>
                            <td className="px-4 py-2 text-sm font-medium text-slate-900">{student.name}</td>
                            <td className="px-4 py-2 text-sm text-slate-600">{student.service}</td>
                            <td className="px-4 py-2 text-right text-sm font-semibold text-slate-900">{student.amount}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">
                  Select a month to view invoice details.
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
