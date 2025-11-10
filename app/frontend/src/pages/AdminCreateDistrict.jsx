import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";

import { createDistrict } from "../api/adminDistricts";

const initialFormValues = {
  company_name: "",
  contact_name: "",
  contact_email: "",
  phone_number: "",
  mailing_address: {
    street: "",
    city: "",
    state: "",
    postal_code: "",
  },
  district_key: "",
};

export default function AdminCreateDistrict() {
  const { getAccessTokenSilently } = useAuth0();
  const navigate = useNavigate();
  const [formValues, setFormValues] = useState(initialFormValues);
  const [formError, setFormError] = useState(null);
  const [creating, setCreating] = useState(false);

  const handleFieldChange = useCallback((event) => {
    const { name, value } = event.target;
    if (name.startsWith("mailing_address.")) {
      const [, field] = name.split(".");
      setFormValues((prev) => ({
        ...prev,
        mailing_address: {
          ...prev.mailing_address,
          [field]: value,
        },
      }));
      return;
    }

    setFormValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleSubmit = useCallback(
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
          mailing_address: {
            street: formValues.mailing_address.street.trim(),
            city: formValues.mailing_address.city.trim(),
            state: formValues.mailing_address.state.trim().toUpperCase(),
            postal_code: formValues.mailing_address.postal_code.trim(),
          },
          district_key: formValues.district_key.trim() || undefined,
        });
        toast.success("District created successfully.");
        setFormValues(initialFormValues);
        navigate("/", { replace: true });
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
    [creating, formValues, getAccessTokenSilently, navigate],
  );

  return (
    <div className="space-y-6 text-slate-700">
      <div>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 transition hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to admin console
        </Link>
        <h2 className="mt-4 text-2xl font-semibold text-slate-900">Create a district</h2>
        <p className="mt-1 text-sm text-slate-600">
          Generate new districts and share the generated access keys with trusted staff members.
        </p>
      </div>

      <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
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

        <div className="md:col-span-2 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="mailing_street">
              Mailing street
            </label>
            <input
              id="mailing_street"
              name="mailing_address.street"
              type="text"
              value={formValues.mailing_address.street}
              onChange={handleFieldChange}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="mailing_city">
              City
            </label>
            <input
              id="mailing_city"
              name="mailing_address.city"
              type="text"
              value={formValues.mailing_address.city}
              onChange={handleFieldChange}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="mailing_state">
              State
            </label>
            <input
              id="mailing_state"
              name="mailing_address.state"
              type="text"
              value={formValues.mailing_address.state}
              onChange={handleFieldChange}
              maxLength={2}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500" htmlFor="mailing_postal">
              ZIP code
            </label>
            <input
              id="mailing_postal"
              name="mailing_address.postal_code"
              type="text"
              value={formValues.mailing_address.postal_code}
              onChange={handleFieldChange}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
            />
          </div>
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
    </div>
  );
}
