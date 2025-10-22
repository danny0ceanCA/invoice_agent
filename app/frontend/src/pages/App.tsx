import { useState } from "react";
import VendorDashboard from "./VendorDashboard.jsx";

const tabs = [
  { key: "vendor", label: "Vendor", component: <VendorDashboard /> },
  {
    key: "district",
    label: "District",
    component: (
      <div className="text-slate-600">
        District analytics and approvals are coming soon.
      </div>
    ),
  },
  {
    key: "admin",
    label: "Admin",
    component: (
      <div className="text-slate-600">
        Administrative tooling for dataset profiles will land shortly.
      </div>
    ),
  },
];

export function App() {
  const [active, setActive] = useState("vendor");
  const activeTab = tabs.find((tab) => tab.key === active) ?? tabs[0];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <h1 className="text-xl font-semibold">ASCS Invoice Automation</h1>
          <nav className="flex gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                className={`rounded px-3 py-1 text-sm font-medium transition hover:bg-slate-100 ${
                  active === tab.key ? "bg-slate-200" : ""
                }`}
                onClick={() => setActive(tab.key)}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          {activeTab.component}
        </div>
      </main>
    </div>
  );
}
