import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import {
  fetchVendorDistrictLink,
  registerVendorDistrictKey,
} from "../api/vendors";

function normalizeDistrictKey(value = "") {
  const cleaned = value.replace(/[^0-9a-z]/gi, "").toUpperCase();
  if (!cleaned) {
    return "";
  }

  return cleaned
    .match(/.{1,4}/g)
    .map((segment) => segment.toUpperCase())
    .join("-");
}

export default function VendorDistrictKeys() {
  const { isAuthenticated, getAccessTokenSilently, loginWithRedirect } = useAuth0();
  const navigate = useNavigate();

  const [linkDetails, setLinkDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [formValue, setFormValue] = useState("");
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const normalizedFormValue = useMemo(() => normalizeDistrictKey(formValue), [formValue]);

  const loadDistrictLink = useCallback(async () => {
    if (!isAuthenticated) {
      setLinkDetails(null);
      setLoadError(null);
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const token = await getAccessTokenSilently();
      const details = await fetchVendorDistrictLink(token);
      setLinkDetails(details);
    } catch (error) {
      console.error("vendor_district_link_load_failed", error);
      setLinkDetails(null);
      setLoadError("We couldn't load your district key information. Please try again later.");
    } finally {
      setLoading(false);
    }
  }, [getAccessTokenSilently, isAuthenticated]);

  useEffect(() => {
    loadDistrictLink();
  }, [loadDistrictLink]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    const normalized = normalizedFormValue;
    if (!normalized) {
      setFormError("Enter the district access key provided by your district contact.");
      return;
    }

    setFormError(null);
    setIsSubmitting(true);
    try {
      const token = await getAccessTokenSilently();
      const details = await registerVendorDistrictKey(token, { district_key: normalized });
      setLinkDetails(details);
      setFormValue("");
      toast.success("District key registered.");
    } catch (error) {
      console.error("vendor_district_key_register_failed", error);
      const message =
        error?.message ?? "We couldn't register that district key. Please verify the value and try again.";
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm text-slate-600">Log in to manage your district keys.</p>
            <button
              type="button"
              onClick={() => loginWithRedirect()}
              className="mt-4 inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600"
            >
              Log in with Auth0
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">District keys</h1>
            <p className="mt-1 text-sm text-slate-600">
              Link your workspace to a district by registering the secure key they share with you.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/")}
            className="inline-flex items-center rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Back to workspace
          </button>
        </header>

        <section className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Registered district keys</h2>
              <button
                type="button"
                onClick={loadDistrictLink}
                className="text-sm font-medium text-amber-600 transition hover:text-amber-700"
              >
                Refresh
              </button>
            </div>
            <div className="mt-4 text-sm text-slate-600">
              {loading ? (
                <p>Loading district keys…</p>
              ) : loadError ? (
                <p className="text-red-600">{loadError}</p>
              ) : linkDetails?.is_linked ? (
                <div className="space-y-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Connected district</p>
                    <p className="mt-1 font-medium text-slate-900">{linkDetails.district_name}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Registered key</p>
                    <p className="mt-1 rounded bg-slate-100 px-3 py-2 font-mono text-sm text-slate-900">
                      {linkDetails.district_key}
                    </p>
                  </div>
                  <p className="text-xs text-slate-500">
                    Need to switch districts? Enter a new key below and we'll update your connection immediately.
                  </p>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-4 text-amber-800">
                  <p className="font-medium">No district key registered</p>
                  <p className="mt-1 text-xs text-amber-700">
                    Register the key provided by your district to unlock invoice submissions.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">Register a district key</h2>
            <p className="mt-1 text-sm text-slate-600">
              Paste the secure key from your district. We'll verify it and connect your workspace.
            </p>
            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700" htmlFor="district_key">
                  District access key
                </label>
                <input
                  id="district_key"
                  type="text"
                  name="district_key"
                  value={normalizedFormValue}
                  onChange={(event) => setFormValue(event.target.value)}
                  placeholder="ABCD-EFGH-IJKL"
                  autoComplete="off"
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm uppercase tracking-widest text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
              {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-500">
                  Registering a new key will replace your current district connection.
                </p>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center rounded-full bg-amber-500 px-5 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSubmitting ? "Registering…" : "Register key"}
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}
