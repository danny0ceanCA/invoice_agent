import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Users2 } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";

import { createDistrict, listDistricts } from "../api/adminDistricts";

export default function AdminDashboard({ currentUser }) {
  const { getAccessTokenSilently } = useAuth0();
  const [districts, setDistricts] = useState([]);
  const [districtsLoading, setDistrictsLoading] = useState(false);
  const [districtsError, setDistrictsError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState(null);
  const [formValues, setFormValues] = useState({
    company_name: "",
    contact_name: "",
    contact_email: "",
    phone_number: "",
    mailing_address: "",
    district_key: "",
  });

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

  const handleFieldChange = useCallback((event) => {
    const { name, value } = event.target;
    setFormValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleCreateDistrict = useCallback(
    async (event) => {
      event.preventDefault();
      if (creating) {
        return;
      }

      const trimmedName = formValues.company_name.trim();
      if (!trimmedName) {
        setFormError("District name is required.");
        return;
      }

      setCreating(true);
      setFormError(null);
      try {
        const token = await getAccessTokenSilently();
        await createDistrict(token, {
          company_name: trimmedName,
          contact_name: formValues.contact_name.trim(),
          contact_email: formValues.contact_email.trim(),
          phone_number: formValues.phone_number.trim(),
          mailing_address: formValues.mailing_address.trim(),
          district_key: formValues.district_key.trim() || undefined,
        });
        toast.success("District created successfully.");
        setFormValues({
          company_name: "",
          contact_name: "",
          contact_email: "",
          phone_number: "",
          mailing_address: "",
          district_key: "",
        });
        await loadDistricts();
      } catch (error) {
        console.error("admin_create_district_failed", error);
        setFormError(
          error instanceof Error && error.message
            ? error.message
            : "We couldn't create the district. Please verify the details and try again.",
        );
      } finally {
        setCreating(false);
      }
    },
    [creating, formValues, getAccessTokenSilently, loadDistricts],
  );

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
            <h3 className="text-lg font-semibold text-slate-900">Create a district</h3>
            <p className="mt-1 text-sm text-slate-600">
              Generate new districts and share the generated access keys with trusted staff members.
            </p>
            <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={handleCreateDistrict}>
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="company_name">
                  District name
                </label>
                <input
                  id="company_name"
                  name="company_name"
                  type="text"
                  required
                  value={formValues.company_name}
                  onChange={handleFieldChange}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="contact_name">
                  Primary contact
                </label>
                <input
                  id="contact_name"
                  name="contact_name"
                  type="text"
                  value={formValues.contact_name}
                  onChange={handleFieldChange}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="contact_email">
                  Contact email
                </label>
                <input
                  id="contact_email"
                  name="contact_email"
                  type="email"
                  value={formValues.contact_email}
                  onChange={handleFieldChange}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="phone_number">
                  Phone number
                </label>
                <input
                  id="phone_number"
                  name="phone_number"
                  type="text"
                  value={formValues.phone_number}
                  onChange={handleFieldChange}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="mailing_address">
                  Mailing address
                </label>
                <textarea
                  id="mailing_address"
                  name="mailing_address"
                  rows={3}
                  value={formValues.mailing_address}
                  onChange={handleFieldChange}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="district_key">
                  Custom district key (optional)
                </label>
                <input
                  id="district_key"
                  name="district_key"
                  type="text"
                  value={formValues.district_key}
                  onChange={handleFieldChange}
                  placeholder="Leave blank to auto-generate"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>

              <div className="md:col-span-2 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={creating}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  {creating ? "Creating…" : "Create district"}
                </button>
                {formError ? (
                  <span className="text-sm font-medium text-red-600">{formError}</span>
                ) : null}
              </div>
            </form>
          </section>

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

