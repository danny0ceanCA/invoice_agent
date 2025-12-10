import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, KeyRound, Users2 } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";

import { listDistricts } from "../api/adminDistricts";

export default function AdminDashboard({ currentUser }) {
  const { getAccessTokenSilently } = useAuth0();
  const [districts, setDistricts] = useState([]);
  const [districtsLoading, setDistrictsLoading] = useState(false);
  const [districtsError, setDistrictsError] = useState(null);
  const loadDistricts = useCallback(async () => {
    if (currentUser?.role !== "admin") {
      setDistricts([]);
      setDistrictsError(null);
      return;
    }

    setDistrictsLoading(true);
    setDistrictsError(null);
    try {
      const token = await getAccessTokenSilently();
      const data = await listDistricts(token);
      setDistricts(data);
    } catch (error) {
      console.error("admin_list_districts_failed", error);
      setDistricts([]);
      setDistrictsError(
        "We couldn't load existing districts. Please refresh the page and try again.",
      );
    } finally {
      setDistrictsLoading(false);
    }
  }, [currentUser?.role, getAccessTokenSilently]);

  useEffect(() => {
    loadDistricts().catch(() => {});
  }, [loadDistricts]);

  const cards = [
    {
      title: "Vendor Workspace Overview",
      description: "Track vendor enrollments, onboarding progress, and active contracts.",
    },
    {
      title: "District Insights",
      description: "Upcoming releases will surface analytics for approvals, payments, and staffing.",
    },
  ];

  return (
    <div className="space-y-6 text-slate-700">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Admin Console</h2>
        <p className="mt-1 text-sm text-slate-600">
          Manage user access, monitor district and vendor workspaces, and keep your operations running smoothly.
        </p>
      </div>

      {currentUser?.role === "admin" && (
        <div className="grid gap-4 md:grid-cols-3">
          <Link
            to="/admin/users"
            className="group flex h-full flex-col justify-between rounded-xl border border-indigo-100 bg-gradient-to-r from-indigo-50 via-sky-50 to-cyan-50 p-6 text-indigo-900 shadow-sm transition-transform duration-200 ease-out hover:-translate-y-1 hover:shadow-xl"
            aria-label="Open user management dashboard"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-wide text-indigo-600">Administration</p>
                <h3 className="mt-2 text-xl font-semibold text-indigo-950">User Management</h3>
              </div>
              <div className="rounded-full bg-indigo-100 p-2 text-indigo-600">
                <Users2 className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-indigo-700">
              Approve pending accounts, adjust roles, and deactivate access — all in one place.
            </p>
            <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-indigo-600">
              Manage users
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </span>
          </Link>

          <Link
            to="/admin/districts/new"
            className="group flex h-full flex-col justify-between rounded-xl border border-amber-100 bg-gradient-to-r from-amber-50 via-orange-50 to-rose-50 p-6 text-amber-900 shadow-sm transition-transform duration-200 ease-out hover:-translate-y-1 hover:shadow-xl"
            aria-label="Jump to district creation form"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-wide text-amber-600">Provisioning</p>
                <h3 className="mt-2 text-xl font-semibold text-amber-950">District Keys</h3>
              </div>
              <div className="rounded-full bg-amber-100 p-2 text-amber-600">
                <KeyRound className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-amber-700">
              Create districts and generate secure access keys to onboard new education partners.
            </p>
            <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-amber-600">
              Issue district keys
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </span>
          </Link>

          <Link
            to="/admin/analytics"
            className="group flex h-full flex-col justify-between rounded-xl border border-teal-100 bg-gradient-to-r from-teal-50 via-cyan-50 to-slate-50 p-6 text-teal-900 shadow-sm transition-transform duration-200 ease-out hover:-translate-y-1 hover:shadow-xl"
            aria-label="Open system analytics dashboard"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-wide text-teal-600">Observability</p>
                <h3 className="mt-2 text-xl font-semibold text-teal-950">System Analytics</h3>
              </div>
              <div className="rounded-full bg-teal-100 p-2 text-teal-600">
                <BarChart3 className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-teal-800">
              Inspect cache, materialized reports, and prefetch activity across analytics services.
            </p>
            <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-teal-600">
              View system analytics
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </span>
          </Link>

          {cards.map((card) => (
            <div
              key={card.title}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
            >
              <p className="text-sm font-semibold text-slate-900">{card.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{card.description}</p>
            </div>
          ))}
        </div>
      )}

      {currentUser?.role === "admin" ? (
        <div className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900">Existing districts</h3>
              {districtsLoading ? (
                <span className="text-xs text-slate-500">Loading…</span>
              ) : null}
            </div>
            {districtsError ? (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                {districtsError}
              </div>
            ) : districts.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                No districts have been created yet. Use the form above to provision the first one.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {districts.map((district) => (
                  <div
                    key={district.id}
                    className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{district.company_name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {district.contact_name ? `${district.contact_name} • ` : ""}
                        {district.contact_email || "No email provided"}
                      </p>
                    </div>
                    <div className="text-xs">
                      <p className="font-semibold uppercase tracking-widest text-slate-500">Access key</p>
                      <p className="mt-1 font-mono text-sm font-semibold text-amber-700">
                        {district.district_key}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}

