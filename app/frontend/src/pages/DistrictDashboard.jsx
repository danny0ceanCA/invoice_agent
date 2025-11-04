import { useEffect, useMemo, useState } from "react";

const menuItems = [
  {
    key: "vendors",
    label: "Vendors",
    description: "",
    stats: {
      active: 12,
      pending: 3,
    },
  },
  {
    key: "approvals",
    label: "Approvals",
    description:
      "Track outstanding invoice approvals and keep spending aligned with district policies.",
    comingSoon: true,
  },
  {
    key: "analytics",
    label: "Analytics",
    description:
      "Dive into spending trends, utilization rates, and budget forecasts to inform leadership decisions.",
    comingSoon: true,
  },
  {
    key: "settings",
    label: "Settings",
    description:
      "Configure district-wide preferences, notification cadences, and escalation workflows.",
    comingSoon: true,
  },
];

const vendorProfiles = [
  {
    id: "harbor-education",
    name: "Harbor Education Services",
    focus: "Speech Therapy",
    campusesServed: 8,
    teamSize: 14,
    health: "On Track",
    manager: "Alana Ruiz",
    managerTitle: "Account Director",
    email: "alana@harboredu.com",
    phone: "(555) 214-0183",
    summary:
      "Provides bilingual speech therapists and scheduling support across core elementary campuses.",
    highlights: [
      { label: "Active Contracts", value: "3" },
      { label: "Avg. Response", value: "2.1 hrs" },
      { label: "Fill Rate", value: "98%" },
    ],
    invoices: {
      2024: [
        {
          month: "January",
          total: "$18,240",
          status: "Approved",
          processedOn: "Feb 2, 2024",
          pdfUrl: "/invoices/harbor-education/january-2024.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,041" },
            { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$2,996" },
            { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,210" },
            { id: "riley-watts", name: "Riley Watts", service: "SLP", amount: "$2,870" },
          ],
        },
        {
          month: "February",
          total: "$18,240",
          status: "Approved",
          processedOn: "Mar 4, 2024",
          pdfUrl: "/invoices/harbor-education/february-2024.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,041" },
            { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$2,996" },
            { id: "sophia-cabrera", name: "Sophia Cabrera", service: "SLP", amount: "$3,155" },
            { id: "leo-kim", name: "Leo Kim", service: "SLP", amount: "$2,890" },
          ],
        },
        {
          month: "March",
          total: "$19,120",
          status: "In Review",
          processedOn: "Apr 8, 2024",
          pdfUrl: "/invoices/harbor-education/march-2024.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,105" },
            { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$3,020" },
            { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,180" },
            { id: "riley-watts", name: "Riley Watts", service: "SLP", amount: "$2,920" },
          ],
        },
        {
          month: "April",
          total: "$19,120",
          status: "Pending Submission",
          processedOn: "Due May 5, 2024",
          pdfUrl: "/invoices/harbor-education/april-2024-draft.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,120" },
            { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$3,055" },
            { id: "sophia-cabrera", name: "Sophia Cabrera", service: "SLP", amount: "$2,985" },
          ],
        },
      ],
      2023: [
        {
          month: "October",
          total: "$17,880",
          status: "Approved",
          processedOn: "Nov 6, 2023",
          pdfUrl: "/invoices/harbor-education/october-2023.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$2,940" },
            { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,115" },
          ],
        },
        {
          month: "November",
          total: "$17,880",
          status: "Approved",
          processedOn: "Dec 7, 2023",
          pdfUrl: "/invoices/harbor-education/november-2023.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$2,940" },
            { id: "riley-watts", name: "Riley Watts", service: "SLP", amount: "$3,045" },
          ],
        },
        {
          month: "December",
          total: "$18,240",
          status: "Approved",
          processedOn: "Jan 5, 2024",
          pdfUrl: "/invoices/harbor-education/december-2023.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", service: "RN", amount: "$3,005" },
            { id: "jordan-miles", name: "Jordan Miles", service: "RN", amount: "$2,960" },
            { id: "amir-patel", name: "Amir Patel", service: "SLP", amount: "$3,120" },
          ],
        },
      ],
    },
  },
  {
    id: "lumen-learning",
    name: "Lumen Learning Labs",
    focus: "Occupational Therapy",
    campusesServed: 5,
    teamSize: 9,
    health: "Monitoring",
    manager: "David Shah",
    managerTitle: "Engagement Lead",
    email: "david@lumenlabs.io",
    phone: "(555) 907-4410",
    summary:
      "Hybrid onsite and teletherapy support with emphasis on adaptive equipment trainings.",
    highlights: [
      { label: "Active Contracts", value: "2" },
      { label: "Avg. Response", value: "3.8 hrs" },
      { label: "Fill Rate", value: "91%" },
    ],
    invoices: {
      2024: [
        {
          month: "January",
          total: "$12,600",
          status: "Approved",
          processedOn: "Feb 1, 2024",
          pdfUrl: "/invoices/lumen-learning/january-2024.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", service: "OTR", amount: "$2,880" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", service: "OTR", amount: "$2,760" },
            { id: "ian-barnes", name: "Ian Barnes", service: "COTA", amount: "$2,410" },
          ],
        },
        {
          month: "February",
          total: "$12,600",
          status: "Needs Revision",
          processedOn: "Action Required",
          pdfUrl: "/invoices/lumen-learning/february-2024-draft.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", service: "OTR", amount: "$2,880" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", service: "OTR", amount: "$2,760" },
            { id: "ian-barnes", name: "Ian Barnes", service: "COTA", amount: "$2,430" },
            { id: "lena-ford", name: "Lena Ford", service: "COTA", amount: "$2,210" },
          ],
        },
        {
          month: "March",
          total: "$13,050",
          status: "Pending Submission",
          processedOn: "Due Apr 28, 2024",
          pdfUrl: "/invoices/lumen-learning/march-2024-draft.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", service: "OTR", amount: "$2,940" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", service: "OTR", amount: "$2,820" },
            { id: "ian-barnes", name: "Ian Barnes", service: "COTA", amount: "$2,320" },
            { id: "lena-ford", name: "Lena Ford", service: "COTA", amount: "$2,280" },
          ],
        },
      ],
      2023: [
        {
          month: "November",
          total: "$11,980",
          status: "Approved",
          processedOn: "Dec 2, 2023",
          pdfUrl: "/invoices/lumen-learning/november-2023.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", service: "OTR", amount: "$2,760" },
            { id: "ian-barnes", name: "Ian Barnes", service: "COTA", amount: "$2,280" },
          ],
        },
        {
          month: "December",
          total: "$12,250",
          status: "Approved",
          processedOn: "Jan 3, 2024",
          pdfUrl: "/invoices/lumen-learning/december-2023.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", service: "OTR", amount: "$2,820" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", service: "OTR", amount: "$2,700" },
            { id: "ian-barnes", name: "Ian Barnes", service: "COTA", amount: "$2,320" },
          ],
        },
      ],
    },
  },
  {
    id: "northstar-analytics",
    name: "Northstar Analytics",
    focus: "Data & Insights",
    campusesServed: 12,
    teamSize: 6,
    health: "In Procurement",
    manager: "Priya Nandakumar",
    managerTitle: "Partner Success",
    email: "priya@northstar.io",
    phone: "(555) 765-0023",
    summary:
      "Centralizes district assessment data and produces executive dashboards for cabinet review.",
    highlights: [
      { label: "Projects", value: "4" },
      { label: "Avg. Response", value: "1.2 hrs" },
      { label: "Data Refresh", value: "Weekly" },
    ],
    invoices: {
      2024: [
        {
          month: "February",
          total: "$22,400",
          status: "Approved",
          processedOn: "Mar 3, 2024",
          pdfUrl: "/invoices/northstar-analytics/february-2024.pdf",
          students: [
            { id: "data-warehouse", name: "Data Warehouse Support", service: "Data Strategy", amount: "$8,960" },
            { id: "kpi-dashboard", name: "KPI Dashboard Refresh", service: "Analytics", amount: "$7,420" },
          ],
        },
        {
          month: "March",
          total: "$22,400",
          status: "In Review",
          processedOn: "Apr 9, 2024",
          pdfUrl: "/invoices/northstar-analytics/march-2024.pdf",
          students: [
            { id: "data-warehouse", name: "Data Warehouse Support", service: "Data Strategy", amount: "$8,960" },
            { id: "attendance-dashboard", name: "Attendance Dashboard Updates", service: "Analytics", amount: "$7,540" },
            { id: "professional-learning", name: "Professional Learning", service: "Enablement", amount: "$5,920" },
          ],
        },
        {
          month: "April",
          total: "$22,400",
          status: "Pending Submission",
          processedOn: "Due May 10, 2024",
          pdfUrl: "/invoices/northstar-analytics/april-2024-draft.pdf",
          students: [
            { id: "data-warehouse", name: "Data Warehouse Support", service: "Data Strategy", amount: "$8,960" },
            { id: "attendance-dashboard", name: "Attendance Dashboard Updates", service: "Analytics", amount: "$7,540" },
          ],
        },
      ],
      2023: [
        {
          month: "December",
          total: "$21,900",
          status: "Approved",
          processedOn: "Jan 4, 2024",
          pdfUrl: "/invoices/northstar-analytics/december-2023.pdf",
          students: [
            { id: "data-warehouse", name: "Data Warehouse Support", service: "Data Strategy", amount: "$8,760" },
            { id: "attendance-dashboard", name: "Attendance Dashboard Updates", service: "Analytics", amount: "$7,320" },
          ],
        },
      ],
    },
  },
];


export default function DistrictDashboard() {
  const [activeKey, setActiveKey] = useState(menuItems[0].key);
  const [selectedVendorId, setSelectedVendorId] = useState(null);
  const [selectedInvoiceKey, setSelectedInvoiceKey] = useState(null);
  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];
  const selectedVendor = vendorProfiles.find((vendor) => vendor.id === selectedVendorId) ?? null;
  useEffect(() => {
    setSelectedInvoiceKey(null);
  }, [activeKey, selectedVendorId]);

  const activeInvoiceDetails = useMemo(() => {
    if (!selectedVendor || !selectedInvoiceKey) {
      return null;
    }

    const invoiceRecord =
      selectedVendor.invoices[selectedInvoiceKey.year]?.find(
        (invoice) => invoice.month === selectedInvoiceKey.month
      ) ?? null;

    if (!invoiceRecord) {
      return null;
    }

    return {
      ...invoiceRecord,
      year: selectedInvoiceKey.year,
    };
  }, [selectedInvoiceKey, selectedVendor]);

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="lg:w-72 shrink-0">
        <div className="rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700 p-1 shadow-xl">
          <div className="rounded-2xl bg-slate-900/60 backdrop-blur">
            <div className="px-6 py-5">
              <p className="text-sm font-semibold uppercase tracking-widest text-slate-300">
                District Console
              </p>
              <h2 className="mt-2 text-2xl font-bold text-white">Operations Menu</h2>
              <p className="mt-3 text-sm text-slate-300">
                Navigate the tools your district teams use every day.
              </p>
            </div>
            <nav className="space-y-1 px-2 pb-4">
              {menuItems.map((item) => {
                const isActive = activeKey === item.key;
                return (
                  <button
                    key={item.key}
                    onClick={() => setActiveKey(item.key)}
                    className={`group flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70 ${
                      isActive
                        ? "bg-slate-200 text-slate-900 shadow-inner"
                        : "text-slate-200 hover:bg-white/10 hover:text-white"
                    }`}
                    type="button"
                  >
                    <span>{item.label}</span>
                    {isActive && (
                      <span className="rounded-full bg-amber-400/90 px-2 py-0.5 text-xs font-semibold text-slate-900">
                        Active
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      </aside>

      <section className="flex-1 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-amber-500">
              {activeItem.label}
            </p>
            <h3 className="mt-2 text-3xl font-bold text-slate-900">
              {activeItem.label === "Vendors" ? "Vendor Partner Overview" : activeItem.label}
            </h3>
          </div>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
            District View
          </span>
        </header>

        {activeItem.description ? (
          <p className="mt-4 text-base leading-relaxed text-slate-600">
            {activeItem.description}
          </p>
        ) : null}

        {activeItem.key === "vendors" ? (
          <div className="mt-8 space-y-6">
            {!selectedVendor ? (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                  Vendors Active
                </h4>
                <p className="text-xs text-slate-500">
                  Choose a partner to review their invoices this fiscal year.
                </p>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {vendorProfiles.map((vendor) => (
                    <button
                      key={vendor.id}
                      onClick={() => setSelectedVendorId(vendor.id)}
                      className="flex h-full flex-col justify-center rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:border-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
                      type="button"
                    >
                      <p className="text-sm font-semibold text-slate-900">
                        {vendor.name}
                        <span className="block text-xs font-medium text-slate-500 sm:inline"> - Contact: {vendor.manager}</span>
                      </p>
                    </button>
                  ))}
                </div>
              </div>
              ) : activeInvoiceDetails ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <button
                    onClick={() => setSelectedInvoiceKey(null)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    type="button"
                  >
                    <span aria-hidden="true">←</span>
                    Back to {selectedVendor.name} months
                  </button>
                  <button
                    onClick={() => setSelectedVendorId(null)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    type="button"
                  >
                    Change vendor
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-amber-500">{selectedVendor.name}</p>
                    <h4 className="mt-1 text-2xl font-semibold text-slate-900">
                      {activeInvoiceDetails.month} {activeInvoiceDetails.year}
                    </h4>
                    <p className="mt-1 text-sm text-slate-500">
                      Status: {activeInvoiceDetails.status} · Processed {activeInvoiceDetails.processedOn}
                    </p>
                    <p className="text-xs text-slate-500">{selectedVendor.email} • {selectedVendor.phone}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                    <span className="inline-flex items-center rounded-full bg-slate-900 px-3 py-1 text-sm font-semibold text-white">
                      Total {activeInvoiceDetails.total}
                    </span>
                    <a
                      href={activeInvoiceDetails.pdfUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center rounded-full bg-amber-500 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    >
                      Download PDF Invoice
                    </a>
                  </div>
                </div>

                <div className="space-y-3">
                  <h5 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Student services</h5>
                  {activeInvoiceDetails.students?.length ? (
                    <ul className="space-y-3">
                      {activeInvoiceDetails.students.map((entry) => {
                        const invoicePdfBase = activeInvoiceDetails.pdfUrl ?? "";
                        const studentInvoiceUrl = entry.pdfUrl
                          ? entry.pdfUrl
                          : invoicePdfBase
                          ? `${invoicePdfBase.replace(/\.pdf$/, "")}/${entry.id}.pdf`
                          : null;

                        return (
                          <li
                            key={entry.id}
                            className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                          >
                            <div className="flex flex-col gap-2 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
                              <p className="text-sm text-slate-700">
                                <span className="font-semibold text-slate-900">
                                  Student Name: {entry.name}
                                </span>
                                {entry.service ? <span>, Service: {entry.service}</span> : null}
                              </p>
                              <div className="flex items-center gap-3 sm:ml-6">
                                {entry.amount ? (
                                  <span className="font-semibold text-slate-900">{entry.amount}</span>
                                ) : null}
                                {studentInvoiceUrl ? (
                                  <a
                                    href={studentInvoiceUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 transition hover:bg-amber-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                                  >
                                    PDF Invoice
                                  </a>
                                ) : null}
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="text-sm text-slate-500">No student services were reported for this month.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-amber-500">{selectedVendor.name}</p>
                    <h4 className="mt-1 text-2xl font-semibold text-slate-900">Select a month</h4>
                    <p className="mt-1 text-sm text-slate-500">Choose a billing month to review detailed student services.</p>
                  </div>
                  <button
                    onClick={() => setSelectedVendorId(null)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    type="button"
                  >
                    <span aria-hidden="true">←</span>
                    Back to vendors
                  </button>
                </div>

                <div className="space-y-6">
                  {Object.entries(selectedVendor.invoices)
                    .sort(([yearA], [yearB]) => Number(yearB) - Number(yearA))
                    .map(([year, invoices]) => (
                      <div key={year} className="space-y-3">
                        <h5 className="text-sm font-semibold uppercase tracking-wider text-slate-500">{year}</h5>
                        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                          {invoices.map((invoice) => (
                            <button
                              key={`${year}-${invoice.month}`}
                              onClick={() =>
                                setSelectedInvoiceKey({
                                  month: invoice.month,
                                  year: Number(year),
                                })
                              }
                              className="flex h-full flex-col justify-center rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:border-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
                              type="button"
                            >
                              <p className="text-lg font-semibold text-slate-900">
                                {`${invoice.month} - ${invoice.total}`}
                              </p>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>

        ) : (
          <div className="mt-8 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-slate-500">
            <p className="text-sm font-medium">
              {activeItem.comingSoon
                ? "This module is being finalized. Check back soon for rich dashboards and workflows."
                : "Select an option from the menu to get started."}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
