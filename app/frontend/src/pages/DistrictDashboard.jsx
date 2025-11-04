import { useMemo, useState } from "react";

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
          pdfUrl: "#",
          lineItems: [
            {
              student: "Aiden Chen",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,160",
            },
            {
              student: "Gabriela Torres",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,340",
            },
            {
              student: "Logan Price",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$1,936",
            },
            {
              student: "Quinn Foster",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$1,848",
            },
            {
              student: "Serena Hill",
              nurse: "Chloe Diaz",
              rate: "$92/hr",
              monthlyTotal: "$2,208",
            },
          ],
        },
        {
          month: "February",
          total: "$18,240",
          status: "Approved",
          processedOn: "Mar 4, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Aiden Chen",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,070",
            },
            {
              student: "Gabriela Torres",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,430",
            },
            {
              student: "Logan Price",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$1,936",
            },
            {
              student: "Quinn Foster",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$1,848",
            },
            {
              student: "Serena Hill",
              nurse: "Chloe Diaz",
              rate: "$92/hr",
              monthlyTotal: "$2,208",
            },
          ],
        },
        {
          month: "March",
          total: "$19,120",
          status: "In Review",
          processedOn: "Apr 8, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Aiden Chen",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,430",
            },
            {
              student: "Gabriela Torres",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,520",
            },
            {
              student: "Logan Price",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$2,112",
            },
            {
              student: "Quinn Foster",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$1,936",
            },
            {
              student: "Serena Hill",
              nurse: "Chloe Diaz",
              rate: "$92/hr",
              monthlyTotal: "$2,392",
            },
          ],
        },
        {
          month: "April",
          total: "$19,120",
          status: "Pending Submission",
          processedOn: "Due May 5, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Aiden Chen",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,430",
            },
            {
              student: "Gabriela Torres",
              nurse: "Marisol Patel",
              rate: "$90/hr",
              monthlyTotal: "$2,520",
            },
            {
              student: "Logan Price",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$2,024",
            },
            {
              student: "Quinn Foster",
              nurse: "Sanjay Mehta",
              rate: "$88/hr",
              monthlyTotal: "$1,936",
            },
            {
              student: "Serena Hill",
              nurse: "Chloe Diaz",
              rate: "$92/hr",
              monthlyTotal: "$2,392",
            },
          ],
        },
      ],
      2023: [
        {
          month: "October",
          total: "$17,880",
          status: "Approved",
          processedOn: "Nov 6, 2023",
        },
        {
          month: "November",
          total: "$17,880",
          status: "Approved",
          processedOn: "Dec 7, 2023",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Aiden Chen",
              nurse: "Marisol Patel",
              rate: "$88/hr",
              monthlyTotal: "$2,024",
            },
            {
              student: "Gabriela Torres",
              nurse: "Marisol Patel",
              rate: "$88/hr",
              monthlyTotal: "$2,200",
            },
            {
              student: "Logan Price",
              nurse: "Sanjay Mehta",
              rate: "$86/hr",
              monthlyTotal: "$1,890",
            },
            {
              student: "Quinn Foster",
              nurse: "Sanjay Mehta",
              rate: "$86/hr",
              monthlyTotal: "$1,806",
            },
            {
              student: "Serena Hill",
              nurse: "Chloe Diaz",
              rate: "$90/hr",
              monthlyTotal: "$2,160",
            },
          ],
        },
        {
          month: "December",
          total: "$18,240",
          status: "Approved",
          processedOn: "Jan 5, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Aiden Chen",
              nurse: "Marisol Patel",
              rate: "$88/hr",
              monthlyTotal: "$2,112",
            },
            {
              student: "Gabriela Torres",
              nurse: "Marisol Patel",
              rate: "$88/hr",
              monthlyTotal: "$2,288",
            },
            {
              student: "Logan Price",
              nurse: "Sanjay Mehta",
              rate: "$86/hr",
              monthlyTotal: "$1,978",
            },
            {
              student: "Quinn Foster",
              nurse: "Sanjay Mehta",
              rate: "$86/hr",
              monthlyTotal: "$1,806",
            },
            {
              student: "Serena Hill",
              nurse: "Chloe Diaz",
              rate: "$90/hr",
              monthlyTotal: "$2,340",
            },
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
          pdfUrl: "#",
          lineItems: [
            {
              student: "Amelia Rivera",
              nurse: "Jordan Blake",
              rate: "$85/hr",
              monthlyTotal: "$1,870",
            },
            {
              student: "Carlos Mendez",
              nurse: "Jordan Blake",
              rate: "$85/hr",
              monthlyTotal: "$1,700",
            },
            {
              student: "Lila Nguyen",
              nurse: "Priya Singh",
              rate: "$82/hr",
              monthlyTotal: "$1,640",
            },
            {
              student: "Micah Owens",
              nurse: "Priya Singh",
              rate: "$82/hr",
              monthlyTotal: "$1,558",
            },
          ],
        },
        {
          month: "February",
          total: "$12,600",
          status: "Needs Revision",
          processedOn: "Action Required",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Amelia Rivera",
              nurse: "Jordan Blake",
              rate: "$85/hr",
              monthlyTotal: "$1,955",
            },
            {
              student: "Carlos Mendez",
              nurse: "Jordan Blake",
              rate: "$85/hr",
              monthlyTotal: "$1,615",
            },
            {
              student: "Lila Nguyen",
              nurse: "Priya Singh",
              rate: "$82/hr",
              monthlyTotal: "$1,722",
            },
            {
              student: "Micah Owens",
              nurse: "Priya Singh",
              rate: "$82/hr",
              monthlyTotal: "$1,476",
            },
          ],
        },
        {
          month: "March",
          total: "$13,050",
          status: "Pending Submission",
          processedOn: "Due Apr 28, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Amelia Rivera",
              nurse: "Jordan Blake",
              rate: "$85/hr",
              monthlyTotal: "$2,040",
            },
            {
              student: "Carlos Mendez",
              nurse: "Jordan Blake",
              rate: "$85/hr",
              monthlyTotal: "$1,700",
            },
            {
              student: "Lila Nguyen",
              nurse: "Priya Singh",
              rate: "$82/hr",
              monthlyTotal: "$1,722",
            },
            {
              student: "Micah Owens",
              nurse: "Priya Singh",
              rate: "$82/hr",
              monthlyTotal: "$1,558",
            },
          ],
        },
      ],
      2023: [
        {
          month: "November",
          total: "$11,980",
          status: "Approved",
          processedOn: "Dec 2, 2023",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Amelia Rivera",
              nurse: "Jordan Blake",
              rate: "$82/hr",
              monthlyTotal: "$1,640",
            },
            {
              student: "Carlos Mendez",
              nurse: "Jordan Blake",
              rate: "$82/hr",
              monthlyTotal: "$1,476",
            },
            {
              student: "Lila Nguyen",
              nurse: "Priya Singh",
              rate: "$80/hr",
              monthlyTotal: "$1,520",
            },
            {
              student: "Micah Owens",
              nurse: "Priya Singh",
              rate: "$80/hr",
              monthlyTotal: "$1,424",
            },
          ],
        },
        {
          month: "December",
          total: "$12,250",
          status: "Approved",
          processedOn: "Jan 3, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "Amelia Rivera",
              nurse: "Jordan Blake",
              rate: "$82/hr",
              monthlyTotal: "$1,722",
            },
            {
              student: "Carlos Mendez",
              nurse: "Jordan Blake",
              rate: "$82/hr",
              monthlyTotal: "$1,476",
            },
            {
              student: "Lila Nguyen",
              nurse: "Priya Singh",
              rate: "$80/hr",
              monthlyTotal: "$1,520",
            },
            {
              student: "Micah Owens",
              nurse: "Priya Singh",
              rate: "$80/hr",
              monthlyTotal: "$1,328",
            },
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
          pdfUrl: "#",
          lineItems: [
            {
              student: "District Data Warehouse",
              nurse: "Analytics Pod A",
              rate: "$140/hr",
              monthlyTotal: "$5,600",
            },
            {
              student: "Intervention Dashboard",
              nurse: "Analytics Pod B",
              rate: "$140/hr",
              monthlyTotal: "$4,900",
            },
            {
              student: "Attendance Insights",
              nurse: "Analytics Pod C",
              rate: "$138/hr",
              monthlyTotal: "$4,554",
            },
            {
              student: "Assessment Sync",
              nurse: "Analytics Pod A",
              rate: "$140/hr",
              monthlyTotal: "$4,760",
            },
          ],
        },
        {
          month: "March",
          total: "$22,400",
          status: "In Review",
          processedOn: "Apr 9, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "District Data Warehouse",
              nurse: "Analytics Pod A",
              rate: "$140/hr",
              monthlyTotal: "$5,740",
            },
            {
              student: "Intervention Dashboard",
              nurse: "Analytics Pod B",
              rate: "$140/hr",
              monthlyTotal: "$4,760",
            },
            {
              student: "Attendance Insights",
              nurse: "Analytics Pod C",
              rate: "$138/hr",
              monthlyTotal: "$4,554",
            },
            {
              student: "Assessment Sync",
              nurse: "Analytics Pod A",
              rate: "$140/hr",
              monthlyTotal: "$4,940",
            },
          ],
        },
        {
          month: "April",
          total: "$22,400",
          status: "Pending Submission",
          processedOn: "Due May 10, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "District Data Warehouse",
              nurse: "Analytics Pod A",
              rate: "$140/hr",
              monthlyTotal: "$5,600",
            },
            {
              student: "Intervention Dashboard",
              nurse: "Analytics Pod B",
              rate: "$140/hr",
              monthlyTotal: "$4,900",
            },
            {
              student: "Attendance Insights",
              nurse: "Analytics Pod C",
              rate: "$138/hr",
              monthlyTotal: "$4,416",
            },
            {
              student: "Assessment Sync",
              nurse: "Analytics Pod A",
              rate: "$140/hr",
              monthlyTotal: "$4,760",
            },
          ],
        },
      ],
      2023: [
        {
          month: "December",
          total: "$21,900",
          status: "Approved",
          processedOn: "Jan 4, 2024",
          pdfUrl: "#",
          lineItems: [
            {
              student: "District Data Warehouse",
              nurse: "Analytics Pod A",
              rate: "$138/hr",
              monthlyTotal: "$5,244",
            },
            {
              student: "Intervention Dashboard",
              nurse: "Analytics Pod B",
              rate: "$138/hr",
              monthlyTotal: "$4,554",
            },
            {
              student: "Attendance Insights",
              nurse: "Analytics Pod C",
              rate: "$136/hr",
              monthlyTotal: "$4,216",
            },
            {
              student: "Assessment Sync",
              nurse: "Analytics Pod A",
              rate: "$138/hr",
              monthlyTotal: "$4,554",
            },
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

function VendorInvoiceDetail({ selectedVendor, selectedInvoice, onBack }) {
  const invoiceYearKey = selectedInvoice.year.toString();
  const invoiceRecord =
    selectedVendor.invoices[invoiceYearKey]?.find(
      (invoice) => invoice.month === selectedInvoice.label
    ) ?? null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-amber-300 hover:text-amber-700"
        >
          ← Back to months
        </button>
        {invoiceRecord ? (
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              statusStyles[invoiceRecord.status] ?? "bg-slate-100 text-slate-600"
            }`}
          >
            {invoiceRecord.status}
          </span>
        ) : (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">
            No Invoice
          </span>
        )}
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              {selectedInvoice.label}
            </p>
            <h4 className="mt-2 text-2xl font-bold text-slate-900">
              {selectedVendor.name}
            </h4>
            <p className="mt-1 text-sm text-slate-500">Fiscal Year {selectedInvoice.year}</p>
          </div>
          {invoiceRecord ? (
            <div className="flex flex-col items-start gap-3 text-left lg:items-end">
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">
                  Monthly Total
                </p>
                <p className="text-2xl font-semibold text-slate-900">
                  {invoiceRecord.total}
                </p>
                <p className="text-xs text-slate-500">{invoiceRecord.processedOn}</p>
              </div>
              {invoiceRecord.pdfUrl ? (
                <a
                  href={invoiceRecord.pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 transition hover:border-amber-300 hover:text-amber-700"
                >
                  Download PDF Invoice
                </a>
              ) : (
                <span className="inline-flex items-center gap-2 rounded-lg border border-dashed border-slate-200 px-4 py-2 text-xs font-semibold text-slate-400">
                  PDF invoice unavailable
                </span>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {invoiceRecord ? (
        <div className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Student
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Nurse
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Rate
                </th>
                <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Monthly Total
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {invoiceRecord.lineItems?.length ? (
                invoiceRecord.lineItems.map((item, index) => (
                  <tr key={`${selectedVendor.id}-${selectedInvoice.label}-${index}`}>
                    <td className="px-6 py-4 text-sm font-medium text-slate-900">
                      {item.student}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">{item.nurse}</td>
                    <td className="px-6 py-4 text-sm text-slate-600">{item.rate}</td>
                    <td className="px-6 py-4 text-right text-sm font-semibold text-slate-900">
                      {item.monthlyTotal}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    className="px-6 py-6 text-center text-sm text-slate-500"
                    colSpan={4}
                  >
                    No student billing records were provided for this invoice.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
          No invoice submission has been recorded for this month yet.
        </div>
      )}
    </div>
  );
}

export default function DistrictDashboard() {
  const [activeKey, setActiveKey] = useState(menuItems[0].key);
  const [selectedVendorId, setSelectedVendorId] = useState(null);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];
  const selectedVendor = vendorProfiles.find((vendor) => vendor.id === selectedVendorId) ?? null;
  const fiscalMonths = useMemo(() => fiscalMonthsThroughCurrent(), []);
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
          <div className="mt-8">
            {selectedVendor ? (
              <div className="space-y-4">
                <div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedVendorId(null);
                      setSelectedInvoice(null);
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-amber-300 hover:text-amber-700"
                  >
                    ← Back to vendors
                  </button>
                </div>

                {selectedInvoice ? (
                  <VendorInvoiceDetail
                    onBack={() => setSelectedInvoice(null)}
                    selectedInvoice={selectedInvoice}
                    selectedVendor={selectedVendor}
                  />
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {fiscalMonths.map(({ year, label }) => {
                      const invoiceYearKey = year.toString();
                      const invoiceRecord =
                        selectedVendor.invoices[invoiceYearKey]?.find(
                          (invoice) => invoice.month === label
                        ) ?? null;

                      return (
                        <button
                          key={`${selectedVendor.id}-${invoiceYearKey}-${label}`}
                          type="button"
                          onClick={() =>
                            setSelectedInvoice({ year, label })
                          }
                          className="flex h-full flex-col gap-3 rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm transition hover:border-amber-300 hover:shadow-md"
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
                              <span className="mt-auto inline-flex items-center gap-1 text-xs font-semibold text-amber-600">
                                View student billing →
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
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                    Vendors Active
                  </h4>
                  <p className="text-xs text-slate-500">
                    Choose a partner to review their invoices this fiscal year.
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {vendorProfiles.map((vendor) => (
                    <button
                      key={vendor.id}
                      onClick={() => {
                        setSelectedVendorId(vendor.id);
                        setSelectedInvoice(null);
                      }}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left transition hover:border-slate-300"
                      type="button"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-slate-900">{vendor.name}</span>
                        <span className="text-xs font-medium text-slate-500">{vendor.health}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{vendor.focus}</p>
                      <p className="mt-3 text-xs text-slate-400">
                        {vendor.campusesServed} campuses • {vendor.teamSize} specialists
                      </p>
                    </button>
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
