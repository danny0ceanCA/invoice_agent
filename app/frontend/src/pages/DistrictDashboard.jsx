import { useEffect, useMemo, useState } from "react";

const menuItems = [
  {
    key: "vendors",
    label: "Vendors",
    description:
      "Review vendor submissions, approve new partnerships, and monitor contract health across the district.",
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
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$92/hr" },
            { id: "jordan-miles", name: "Jordan Miles", nurse: "Lisa Gomez, RN", rate: "$92/hr" },
            { id: "amir-patel", name: "Amir Patel", nurse: "Courtney Blake, SLP", rate: "$88/hr" },
            { id: "riley-watts", name: "Riley Watts", nurse: "Courtney Blake, SLP", rate: "$88/hr" },
          ],
        },
        {
          month: "February",
          total: "$18,240",
          status: "Approved",
          processedOn: "Mar 4, 2024",
          pdfUrl: "/invoices/harbor-education/february-2024.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$92/hr" },
            { id: "jordan-miles", name: "Jordan Miles", nurse: "Lisa Gomez, RN", rate: "$92/hr" },
            { id: "sophia-cabrera", name: "Sophia Cabrera", nurse: "Courtney Blake, SLP", rate: "$90/hr" },
            { id: "leo-kim", name: "Leo Kim", nurse: "Courtney Blake, SLP", rate: "$90/hr" },
          ],
        },
        {
          month: "March",
          total: "$19,120",
          status: "In Review",
          processedOn: "Apr 8, 2024",
          pdfUrl: "/invoices/harbor-education/march-2024.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$94/hr" },
            { id: "jordan-miles", name: "Jordan Miles", nurse: "Lisa Gomez, RN", rate: "$94/hr" },
            { id: "amir-patel", name: "Amir Patel", nurse: "Courtney Blake, SLP", rate: "$90/hr" },
            { id: "riley-watts", name: "Riley Watts", nurse: "Courtney Blake, SLP", rate: "$90/hr" },
          ],
        },
        {
          month: "April",
          total: "$19,120",
          status: "Pending Submission",
          processedOn: "Due May 5, 2024",
          pdfUrl: "/invoices/harbor-education/april-2024-draft.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$94/hr" },
            { id: "jordan-miles", name: "Jordan Miles", nurse: "Lisa Gomez, RN", rate: "$94/hr" },
            { id: "sophia-cabrera", name: "Sophia Cabrera", nurse: "Courtney Blake, SLP", rate: "$92/hr" },
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
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$90/hr" },
            { id: "amir-patel", name: "Amir Patel", nurse: "Courtney Blake, SLP", rate: "$86/hr" },
          ],
        },
        {
          month: "November",
          total: "$17,880",
          status: "Approved",
          processedOn: "Dec 7, 2023",
          pdfUrl: "/invoices/harbor-education/november-2023.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$90/hr" },
            { id: "riley-watts", name: "Riley Watts", nurse: "Courtney Blake, SLP", rate: "$86/hr" },
          ],
        },
        {
          month: "December",
          total: "$18,240",
          status: "Approved",
          processedOn: "Jan 5, 2024",
          pdfUrl: "/invoices/harbor-education/december-2023.pdf",
          students: [
            { id: "maya-chen", name: "Maya Chen", nurse: "Lisa Gomez, RN", rate: "$90/hr" },
            { id: "jordan-miles", name: "Jordan Miles", nurse: "Lisa Gomez, RN", rate: "$90/hr" },
            { id: "amir-patel", name: "Amir Patel", nurse: "Courtney Blake, SLP", rate: "$88/hr" },
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
            { id: "elliot-ramirez", name: "Elliot Ramirez", nurse: "Hannah Ortiz, OTR", rate: "$84/hr" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", nurse: "Hannah Ortiz, OTR", rate: "$84/hr" },
            { id: "ian-barnes", name: "Ian Barnes", nurse: "Marcus Lee, COTA", rate: "$78/hr" },
          ],
        },
        {
          month: "February",
          total: "$12,600",
          status: "Needs Revision",
          processedOn: "Action Required",
          pdfUrl: "/invoices/lumen-learning/february-2024-draft.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", nurse: "Hannah Ortiz, OTR", rate: "$84/hr" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", nurse: "Hannah Ortiz, OTR", rate: "$84/hr" },
            { id: "ian-barnes", name: "Ian Barnes", nurse: "Marcus Lee, COTA", rate: "$78/hr" },
            { id: "lena-ford", name: "Lena Ford", nurse: "Marcus Lee, COTA", rate: "$78/hr" },
          ],
        },
        {
          month: "March",
          total: "$13,050",
          status: "Pending Submission",
          processedOn: "Due Apr 28, 2024",
          pdfUrl: "/invoices/lumen-learning/march-2024-draft.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", nurse: "Hannah Ortiz, OTR", rate: "$86/hr" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", nurse: "Hannah Ortiz, OTR", rate: "$86/hr" },
            { id: "lena-ford", name: "Lena Ford", nurse: "Marcus Lee, COTA", rate: "$80/hr" },
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
            { id: "elliot-ramirez", name: "Elliot Ramirez", nurse: "Hannah Ortiz, OTR", rate: "$82/hr" },
            { id: "ian-barnes", name: "Ian Barnes", nurse: "Marcus Lee, COTA", rate: "$76/hr" },
          ],
        },
        {
          month: "December",
          total: "$12,250",
          status: "Approved",
          processedOn: "Jan 3, 2024",
          pdfUrl: "/invoices/lumen-learning/december-2023.pdf",
          students: [
            { id: "elliot-ramirez", name: "Elliot Ramirez", nurse: "Hannah Ortiz, OTR", rate: "$82/hr" },
            { id: "tessa-nguyen", name: "Tessa Nguyen", nurse: "Hannah Ortiz, OTR", rate: "$82/hr" },
            { id: "ian-barnes", name: "Ian Barnes", nurse: "Marcus Lee, COTA", rate: "$76/hr" },
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
            { id: "data-warehouse", name: "Data Warehouse Support", nurse: "Priya Nandakumar", rate: "$140/hr" },
            { id: "kpi-dashboard", name: "KPI Dashboard Refresh", nurse: "Noah Jenkins", rate: "$136/hr" },
          ],
        },
        {
          month: "March",
          total: "$22,400",
          status: "In Review",
          processedOn: "Apr 9, 2024",
          pdfUrl: "/invoices/northstar-analytics/march-2024.pdf",
          students: [
            { id: "data-warehouse", name: "Data Warehouse Support", nurse: "Priya Nandakumar", rate: "$140/hr" },
            { id: "attendance-dashboard", name: "Attendance Dashboard Updates", nurse: "Noah Jenkins", rate: "$136/hr" },
            { id: "professional-learning", name: "Professional Learning", nurse: "Anika Shah", rate: "$132/hr" },
          ],
        },
        {
          month: "April",
          total: "$22,400",
          status: "Pending Submission",
          processedOn: "Due May 10, 2024",
          pdfUrl: "/invoices/northstar-analytics/april-2024-draft.pdf",
          students: [
            { id: "data-warehouse", name: "Data Warehouse Support", nurse: "Priya Nandakumar", rate: "$140/hr" },
            { id: "attendance-dashboard", name: "Attendance Dashboard Updates", nurse: "Noah Jenkins", rate: "$136/hr" },
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
            { id: "data-warehouse", name: "Data Warehouse Support", nurse: "Priya Nandakumar", rate: "$138/hr" },
            { id: "attendance-dashboard", name: "Attendance Dashboard Updates", nurse: "Noah Jenkins", rate: "$134/hr" },
          ],
        },
      ],
    },
  },
];

const statusStyles = {
  Approved: "bg-emerald-100 text-emerald-700",
  "In Review": "bg-amber-100 text-amber-700",
  "Pending Submission": "bg-slate-100 text-slate-600",
  "Needs Revision": "bg-rose-100 text-rose-700",
};

const fiscalStartMonthIndex = 6; // July
const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const fiscalMonthsThroughCurrent = () => {
  const today = new Date();
  const currentMonthIndex = today.getMonth();
  const currentYear = today.getFullYear();
  const startYear =
    currentMonthIndex >= fiscalStartMonthIndex ? currentYear : currentYear - 1;

  const months = [];
  let workingMonth = fiscalStartMonthIndex;
  let workingYear = startYear;

  while (true) {
    months.push({
      year: workingYear,
      label: monthNames[workingMonth],
    });

    if (workingMonth === currentMonthIndex && workingYear === currentYear) {
      break;
    }

    workingMonth += 1;
    if (workingMonth > 11) {
      workingMonth = 0;
      workingYear += 1;
    }
  }

  return months;
};

export default function DistrictDashboard() {
  const [activeKey, setActiveKey] = useState(menuItems[0].key);
  const [selectedVendorId, setSelectedVendorId] = useState(null);
  const [selectedInvoiceKey, setSelectedInvoiceKey] = useState(null);
  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];
  const selectedVendor = vendorProfiles.find((vendor) => vendor.id === selectedVendorId) ?? null;
  const fiscalMonths = useMemo(() => fiscalMonthsThroughCurrent(), []);
  const fiscalStartYear = fiscalMonths[0]?.year;
  const fiscalEndYear = fiscalMonths[fiscalMonths.length - 1]?.year;
  const fiscalYearLabel = useMemo(() => {
    if (typeof fiscalStartYear === "number" && typeof fiscalEndYear === "number") {
      return `Fiscal Year ${fiscalStartYear}-${(fiscalEndYear % 100).toString().padStart(2, "0")}`;
    }
    return "Current Fiscal Year";
  }, [fiscalEndYear, fiscalStartYear]);

  useEffect(() => {
    setSelectedInvoiceKey(null);
  }, [activeKey, selectedVendorId]);

  const selectedInvoiceDetails = useMemo(() => {
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
                        ? "bg-white text-slate-900 shadow-lg"
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

        <p className="mt-4 text-base leading-relaxed text-slate-600">
          {activeItem.description}
        </p>

        {activeItem.key === "vendors" ? (
          <div className="mt-8 flex flex-col gap-6 lg:flex-row">
            <aside className="lg:w-80 space-y-3">
              <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                Vendors Active
              </h4>
              <p className="text-xs text-slate-500">
                Choose a partner to review their invoices this fiscal year.
              </p>
              {vendorProfiles.map((vendor) => {
                const isSelected = vendor.id === selectedVendorId;
                return (
                  <button
                    key={vendor.id}
                    onClick={() => setSelectedVendorId(vendor.id)}
                    className={`w-full rounded-2xl border px-5 py-4 text-left transition ${
                      isSelected
                        ? "border-amber-400 bg-amber-50 shadow-md"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                    type="button"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-900">{vendor.name}</span>
                      <span
                        className={`text-xs font-medium ${
                          isSelected ? "text-amber-700" : "text-slate-500"
                        }`}
                      >
                        {vendor.health}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{vendor.focus}</p>
                    <p className="mt-3 text-xs text-slate-400">
                      {vendor.campusesServed} campuses • {vendor.teamSize} specialists
                    </p>
                  </button>
                );
              })}
            </aside>

            <div className="flex-1">
              {selectedVendor ? (
                <div className="space-y-5">
                  <div>
                    <h4 className="text-xl font-semibold text-slate-900">{selectedVendor.name}</h4>
                    <p className="text-sm text-slate-500">{fiscalYearLabel}</p>
                    <p className="mt-2 text-sm text-slate-500">
                      Select a month below to review invoice activity.
                    </p>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {fiscalMonths.map(({ year, label }) => {
                      const invoiceYearKey = year.toString();
                      const invoiceRecord =
                        selectedVendor.invoices[invoiceYearKey]?.find(
                          (invoice) => invoice.month === label
                        ) ?? null;

                      const isSelectedInvoice =
                        invoiceRecord &&
                        selectedInvoiceKey?.month === label &&
                        selectedInvoiceKey?.year === invoiceYearKey;

                      return (
                        <button
                          key={`${selectedVendor.id}-${invoiceYearKey}-${label}`}
                          type="button"
                          onClick={() => {
                            if (invoiceRecord) {
                              setSelectedInvoiceKey({ month: label, year: invoiceYearKey });
                            }
                          }}
                          disabled={!invoiceRecord}
                          className={`flex h-full flex-col gap-3 rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm transition ${
                            invoiceRecord
                              ? "hover:border-amber-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                              : "cursor-not-allowed opacity-60"
                          } ${isSelectedInvoice ? "border-amber-400 ring-2 ring-amber-200" : ""}`}
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                {label}
                              </p>
                              <p className="mt-1 text-sm text-slate-500">{year}</p>
                            </div>
                            {invoiceRecord ? (
                              <span
                                className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                                  statusStyles[invoiceRecord.status] ??
                                  "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {invoiceRecord.status}
                              </span>
                            ) : (
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
                                No Invoice
                              </span>
                            )}
                          </div>
                          {invoiceRecord ? (
                            <>
                              <p className="text-lg font-semibold text-slate-900">
                                {invoiceRecord.total}
                              </p>
                              <p className="text-xs text-slate-500">{invoiceRecord.processedOn}</p>
                              <span
                                className={`mt-auto inline-flex items-center text-xs font-semibold ${
                                  isSelectedInvoice ? "text-amber-700" : "text-slate-500"
                                }`}
                              >
                                {isSelectedInvoice ? "Selected" : "View details"}
                              </span>
                            </>
                          ) : (
                            <p className="text-sm text-slate-500">
                              No submission recorded for this month yet.
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  {selectedInvoiceDetails ? (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <h5 className="text-lg font-semibold text-slate-900">
                            {selectedInvoiceDetails.month} {selectedInvoiceDetails.year} Services
                          </h5>
                          <p className="text-sm text-slate-500">
                            Students served by {selectedVendor.name}
                          </p>
                        </div>
                        <a
                          href={selectedInvoiceDetails.pdfUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center justify-center rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                        >
                          Download PDF Invoice
                        </a>
                      </div>

                      {selectedInvoiceDetails.students?.length ? (
                        <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
                          <table className="min-w-full divide-y divide-slate-200 text-left">
                            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                              <tr>
                                <th scope="col" className="px-4 py-3">
                                  Student
                                </th>
                                <th scope="col" className="px-4 py-3">
                                  Nurse
                                </th>
                                <th scope="col" className="px-4 py-3">
                                  Rate
                                </th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 text-sm">
                              {selectedInvoiceDetails.students.map((entry) => (
                                <tr key={entry.id} className="bg-white">
                                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                                    {entry.name}
                                  </td>
                                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{entry.nurse}</td>
                                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{entry.rate}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="mt-4 text-sm text-slate-500">
                          No student services were reported for this month.
                        </p>
                      )}

                      <div className="mt-6 flex items-center justify-between rounded-xl bg-slate-900 px-4 py-3 text-sm text-slate-100">
                        <span>Total billed amount</span>
                        <span className="text-lg font-semibold text-white">
                          {selectedInvoiceDetails.total}
                        </span>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="flex h-full min-h-[320px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
                  <p className="text-sm font-medium text-slate-500">
                    Select a vendor to view monthly invoices.
                  </p>
                </div>
              )}
            </div>
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
