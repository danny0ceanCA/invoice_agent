import { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import VendorDashboard from "./VendorDashboard.jsx";
import DistrictDashboard from "./DistrictDashboard.jsx";

const tabs = [
  { key: "vendor", label: "Vendor", component: <VendorDashboard /> },
  {
    key: "district",
    label: "District",
    component: <DistrictDashboard />,
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
  const { isAuthenticated, isLoading, loginWithRedirect, logout, user } = useAuth0();
  const displayName = user?.name ?? user?.email ?? "Account";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-6 px-6 py-4">
          <h1 className="text-xl font-semibold">ASCS Invoice Automation</h1>
          <div className="flex items-center gap-4">
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
            <div className="flex items-center gap-3">
              {isAuthenticated ? (
                <>
                  <span className="text-sm text-slate-600">Signed in as {displayName}</span>
                  <button
                    type="button"
                    className="rounded border border-slate-200 px-3 py-1 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
                    onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                  >
                    Log out
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="rounded bg-amber-500 px-3 py-1 text-sm font-semibold text-white shadow transition hover:bg-amber-600"
                  onClick={() => loginWithRedirect()}
                >
                  Log in
                </button>
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          {isLoading ? (
            <div className="text-sm text-slate-600">Checking session…</div>
          ) : isAuthenticated ? (
            activeTab.component
          ) : (
            <div className="text-sm text-slate-600">
              Please log in to access the invoice automation portal.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
