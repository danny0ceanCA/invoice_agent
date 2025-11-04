import { useEffect, useMemo, useState } from "react";

const vendorDirectory = [
  {
    id: "vendor-1",
    name: "BrightPath Learning",
    category: "Academic Tutoring",
    campuses: 8,
    owner: "Alicia Nguyen",
    phone: "512-555-0198",
    email: "partnerships@brightpathlearning.com",
    spendToDate: "$245,430",
    invoiceHistory: {
      2024: [
        {
          month: "January",
          invoices: 12,
          amount: "$24,530",
          status: "Reconciled",
          updated: "Feb 6",
        },
        {
          month: "February",
          invoices: 10,
          amount: "$21,980",
          status: "Reconciled",
          updated: "Mar 4",
        },
        {
          month: "March",
          invoices: 9,
          amount: "$19,120",
          status: "Pending Review",
          updated: "Apr 2",
        },
        {
          month: "April",
          invoices: 11,
          amount: "$22,845",
          status: "Reconciled",
          updated: "May 6",
        },
        {
          month: "May",
          invoices: 14,
          amount: "$27,910",
          status: "Reconciled",
          updated: "Jun 4",
        },
        {
          month: "June",
          invoices: 8,
          amount: "$16,480",
          status: "Exceptions Logged",
          updated: "Jul 1",
        },
        {
          month: "July",
          invoices: 7,
          amount: "$14,360",
          status: "Pending Review",
          updated: "Aug 5",
        },
        {
          month: "August",
          invoices: 13,
          amount: "$26,770",
          status: "Reconciled",
          updated: "Sep 3",
        },
        {
          month: "September",
          invoices: 10,
          amount: "$20,655",
          status: "Reconciled",
          updated: "Oct 7",
        },
        {
          month: "October",
          invoices: 9,
          amount: "$18,540",
          status: "Pending Review",
          updated: "Nov 4",
        },
        {
          month: "November",
          invoices: 11,
          amount: "$23,715",
          status: "Reconciled",
          updated: "Dec 2",
        },
        {
          month: "December",
          invoices: 8,
          amount: "$16,940",
          status: "In Preparation",
          updated: "Jan 6",
        },
      ],
      2023: [
        {
          month: "November",
          invoices: 10,
          amount: "$21,330",
          status: "Reconciled",
          updated: "Dec 5",
        },
        {
          month: "October",
          invoices: 8,
          amount: "$17,980",
          status: "Reconciled",
          updated: "Nov 3",
        },
        {
          month: "September",
          invoices: 9,
          amount: "$18,720",
          status: "Reconciled",
          updated: "Oct 4",
        },
        {
          month: "August",
          invoices: 12,
          amount: "$24,640",
          status: "Reconciled",
          updated: "Sep 6",
        },
      ],
    },
  },
  {
    id: "vendor-2",
    name: "CampusFuel Nutrition",
    category: "Meal Services",
    campuses: 12,
    owner: "Marcus Tillman",
    phone: "713-555-0124",
    email: "district@campusfuel.com",
    spendToDate: "$312,870",
    invoiceHistory: {
      2024: [
        {
          month: "January",
          invoices: 14,
          amount: "$32,110",
          status: "Reconciled",
          updated: "Feb 2",
        },
        {
          month: "February",
          invoices: 13,
          amount: "$30,425",
          status: "Reconciled",
          updated: "Mar 3",
        },
        {
          month: "March",
          invoices: 15,
          amount: "$34,890",
          status: "Pending Review",
          updated: "Apr 3",
        },
        {
          month: "April",
          invoices: 12,
          amount: "$28,770",
          status: "Reconciled",
          updated: "May 2",
        },
        {
          month: "May",
          invoices: 16,
          amount: "$36,115",
          status: "Reconciled",
          updated: "Jun 3",
        },
        {
          month: "June",
          invoices: 11,
          amount: "$25,940",
          status: "Exceptions Logged",
          updated: "Jul 5",
        },
        {
          month: "July",
          invoices: 12,
          amount: "$27,320",
          status: "Reconciled",
          updated: "Aug 2",
        },
        {
          month: "August",
          invoices: 15,
          amount: "$33,740",
          status: "Pending Review",
          updated: "Sep 4",
        },
      ],
      2023: [
        {
          month: "December",
          invoices: 13,
          amount: "$29,880",
          status: "Reconciled",
          updated: "Jan 4",
        },
        {
          month: "November",
          invoices: 12,
          amount: "$27,540",
          status: "Reconciled",
          updated: "Dec 4",
        },
        {
          month: "October",
          invoices: 11,
          amount: "$25,210",
          status: "Reconciled",
          updated: "Nov 2",
        },
      ],
    },
  },
  {
    id: "vendor-3",
    name: "STEMSpark Workshops",
    category: "Enrichment Programs",
    campuses: 6,
    owner: "Priya Desai",
    phone: "210-555-0173",
    email: "hello@stemspark.org",
    spendToDate: "$128,640",
    invoiceHistory: {
      2024: [
        {
          month: "January",
          invoices: 6,
          amount: "$11,460",
          status: "Reconciled",
          updated: "Feb 7",
        },
        {
          month: "February",
          invoices: 5,
          amount: "$9,820",
          status: "Reconciled",
          updated: "Mar 5",
        },
        {
          month: "March",
          invoices: 6,
          amount: "$11,950",
          status: "Pending Review",
          updated: "Apr 5",
        },
        {
          month: "April",
          invoices: 4,
          amount: "$7,440",
          status: "Reconciled",
          updated: "May 6",
        },
        {
          month: "May",
          invoices: 5,
          amount: "$9,980",
          status: "Reconciled",
          updated: "Jun 5",
        },
        {
          month: "June",
          invoices: 4,
          amount: "$8,210",
          status: "Pending Review",
          updated: "Jul 8",
        },
        {
          month: "July",
          invoices: 4,
          amount: "$8,010",
          status: "In Preparation",
          updated: "Aug 5",
        },
      ],
      2023: [
        {
          month: "December",
          invoices: 5,
          amount: "$9,520",
          status: "Reconciled",
          updated: "Jan 8",
        },
        {
          month: "November",
          invoices: 4,
          amount: "$8,130",
          status: "Reconciled",
          updated: "Dec 7",
        },
        {
          month: "October",
          invoices: 5,
          amount: "$9,270",
          status: "Reconciled",
          updated: "Nov 6",
        },
      ],
    },
  },
];

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

const statusStyles = {
  Reconciled: "border-emerald-100 bg-emerald-50 text-emerald-700",
  "Pending Review": "border-amber-100 bg-amber-50 text-amber-700",
  "Exceptions Logged": "border-rose-100 bg-rose-50 text-rose-700",
  "In Preparation": "border-slate-200 bg-slate-50 text-slate-600",
};

const vendorPanels = [
  { key: "invoices", label: "Invoices" },
  { key: "contracts", label: "Contracts" },
  { key: "performance", label: "Performance" },
];

const defaultVendorYear = (vendor) => {
  const years = Object.keys(vendor.invoiceHistory ?? {});
  return years.sort((a, b) => Number(b) - Number(a))[0];
};

export default function DistrictDashboard() {
  const [activeKey, setActiveKey] = useState(menuItems[0].key);
  const [selectedVendorId, setSelectedVendorId] = useState(vendorDirectory[0].id);
  const [vendorPanel, setVendorPanel] = useState(vendorPanels[0].key);
  const [selectedYear, setSelectedYear] = useState(defaultVendorYear(vendorDirectory[0]));

  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];
  const selectedVendor = vendorDirectory.find((vendor) => vendor.id === selectedVendorId) ?? vendorDirectory[0];

  useEffect(() => {
    setVendorPanel(vendorPanels[0].key);
  }, [selectedVendorId]);

  useEffect(() => {
    const years = Object.keys(selectedVendor.invoiceHistory ?? {}).sort(
      (a, b) => Number(b) - Number(a)
    );
    if (years.length) {
      setSelectedYear((prev) => (years.includes(prev) ? prev : years[0]));
    }
  }, [selectedVendor]);

  const yearsForVendor = useMemo(() => {
    return Object.keys(selectedVendor.invoiceHistory ?? {}).sort((a, b) => Number(b) - Number(a));
  }, [selectedVendor]);

  const monthTiles = selectedVendor.invoiceHistory[selectedYear] ?? [];

  const vendorMetrics = useMemo(
    () => [
      {
        label: "Active Vendors",
        value: vendorDirectory.length,
        helper: "Approved and billing this term.",
      },
      {
        label: "Campuses Served",
        value: vendorDirectory.reduce((total, vendor) => total + vendor.campuses, 0),
        helper: "Across all active partnerships.",
      },
      {
        label: "Annual Spend",
        value: "$686K",
        helper: "Committed with current contracts.",
      },
      {
        label: "Pending Renewals",
        value: 3,
        helper: "Expiring within 90 days.",
      },
    ],
    []
  );

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
          <div className="mt-8 space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {vendorMetrics.map((metric) => (
                <div
                  key={metric.label}
                  className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4 shadow-sm"
                >
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                    {metric.label}
                  </p>
                  <p className="mt-3 text-2xl font-bold text-slate-900">{metric.value}</p>
                  <p className="mt-2 text-xs text-slate-500">{metric.helper}</p>
                </div>
              ))}
            </div>

            <div className="grid gap-6 lg:grid-cols-[320px,1fr] xl:grid-cols-[340px,1fr]">
              <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                      Vendor Directory
                    </p>
                    <h4 className="mt-1 text-lg font-semibold text-slate-900">Active partnerships</h4>
                  </div>
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                    {vendorDirectory.length} Vendors
                  </span>
                </div>
                <div className="mt-4 space-y-2">
                  {vendorDirectory.map((vendor) => {
                    const isSelected = vendor.id === selectedVendor.id;
                    return (
                      <button
                        key={vendor.id}
                        onClick={() => setSelectedVendorId(vendor.id)}
                        className={`w-full rounded-xl border px-4 py-3 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 ${
                          isSelected
                            ? "border-amber-200 bg-amber-50/80 shadow-sm"
                            : "border-slate-200 bg-white hover:border-amber-200/80 hover:bg-amber-50/40"
                        }`}
                        type="button"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{vendor.name}</p>
                            <p className="text-xs text-slate-500">{vendor.category}</p>
                          </div>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                            {vendor.campuses} campuses
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">
                          Lead: {vendor.owner}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-6">
                <div className="rounded-2xl border border-amber-100 bg-amber-50/60 p-6 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-widest text-amber-600">
                        {selectedVendor.category}
                      </p>
                      <h4 className="mt-1 text-2xl font-bold text-amber-900">{selectedVendor.name}</h4>
                      <p className="mt-2 text-sm text-amber-800/80">
                        Serving {selectedVendor.campuses} campuses • {selectedVendor.spendToDate} billed this year
                      </p>
                    </div>
                    <div className="rounded-xl border border-amber-200 bg-white px-4 py-3 text-xs text-amber-800">
                      <p className="font-semibold uppercase tracking-widest">Partnership Lead</p>
                      <p className="mt-1 font-medium">{selectedVendor.owner}</p>
                      <p className="text-[11px] text-amber-700/80">{selectedVendor.email}</p>
                      <p className="text-[11px] text-amber-700/80">{selectedVendor.phone}</p>
                    </div>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {vendorPanels.map((panel) => {
                      const isActive = vendorPanel === panel.key;
                      return (
                        <button
                          key={panel.key}
                          onClick={() => setVendorPanel(panel.key)}
                          type="button"
                          className={`rounded-full px-4 py-1 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60 ${
                            isActive
                              ? "bg-amber-600 text-white shadow"
                              : "bg-white text-amber-700 hover:bg-amber-100"
                          }`}
                        >
                          {panel.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {vendorPanel === "invoices" ? (
                  <div className="grid gap-6 lg:grid-cols-[160px,1fr] xl:grid-cols-[180px,1fr]">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                        Fiscal Years
                      </p>
                      <div className="mt-3 flex flex-col gap-2">
                        {yearsForVendor.map((year) => {
                          const isActive = year === selectedYear;
                          return (
                            <button
                              key={year}
                              onClick={() => setSelectedYear(year)}
                              type="button"
                              className={`rounded-xl px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 ${
                                isActive
                                  ? "bg-white text-amber-700 shadow"
                                  : "text-slate-600 hover:bg-white/60"
                              }`}
                            >
                              {year}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                            Invoice Activity
                          </p>
                          <h5 className="mt-1 text-xl font-semibold text-slate-900">
                            {selectedYear} monthly submissions
                          </h5>
                        </div>
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                          {monthTiles.length} Months
                        </span>
                      </div>
                      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                        {monthTiles.map((period) => {
                          const badgeStyle = statusStyles[period.status] ?? "border-slate-200 bg-slate-50 text-slate-600";
                          return (
                            <div
                              key={`${selectedVendor.id}-${selectedYear}-${period.month}`}
                              className="group rounded-2xl border border-slate-200 bg-white p-4 transition hover:-translate-y-1 hover:border-amber-200 hover:shadow-lg"
                            >
                              <div className="flex items-start justify-between">
                                <div>
                                  <p className="text-sm font-semibold text-slate-900">{period.month}</p>
                                  <p className="text-xs text-slate-500">{period.invoices} invoices submitted</p>
                                </div>
                                <span
                                  className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${badgeStyle}`}
                                >
                                  {period.status}
                                </span>
                              </div>
                              <p className="mt-4 text-2xl font-bold text-slate-900">{period.amount}</p>
                              <p className="mt-2 text-xs text-slate-500">Last updated {period.updated}</p>
                              <button
                                type="button"
                                className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-amber-600 transition hover:text-amber-700"
                              >
                                View invoice packet
                                <span aria-hidden>→</span>
                              </button>
                            </div>
                          );
                        })}
                        {!monthTiles.length && (
                          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
                            No invoice history recorded for {selectedYear} yet.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-10 text-center text-slate-500">
                    Detailed {vendorPanels.find((panel) => panel.key === vendorPanel)?.label.toLowerCase()} dashboards will appear here as they are finalized.
                  </div>
                )}
              </div>
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
