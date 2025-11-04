import { useState } from "react";

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

export default function DistrictDashboard() {
  const [activeKey, setActiveKey] = useState(menuItems[0].key);
  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];

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
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-100 bg-amber-50/70 p-6">
              <p className="text-sm font-semibold uppercase tracking-wider text-amber-700">
                Active Vendors
              </p>
              <p className="mt-3 text-4xl font-bold text-amber-900">
                {activeItem.stats?.active ?? 0}
              </p>
              <p className="mt-2 text-sm text-amber-800/80">
                Vendors currently fulfilling services across your campuses.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
              <p className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                Pending Reviews
              </p>
              <p className="mt-3 text-4xl font-bold text-slate-900">
                {activeItem.stats?.pending ?? 0}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Vendor profiles awaiting district approval to begin billing.
              </p>
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
