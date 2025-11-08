import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";

import { uploadInvoice } from "../api/invoices";
import { listJobs } from "../api/jobs";
import {
  fetchVendorProfile,
  updateVendorProfile,
} from "../api/vendors";
import JobStatusCard from "./JobStatusCard";

const PHONE_DIGIT_LENGTH = 10;
const PHONE_INPUT_PATTERN = /^\(\d{3}\)-\d{3}-\d{4}$/;

function stripPhoneNumber(value = "") {
  return value.replace(/\D/g, "").slice(0, PHONE_DIGIT_LENGTH);
}

function formatPhoneNumberForDisplay(value = "") {
  const digits = stripPhoneNumber(value);
  if (digits.length !== PHONE_DIGIT_LENGTH) {
    return value?.trim?.() ?? "";
  }

  const area = digits.slice(0, 3);
  const prefix = digits.slice(3, 6);
  const lineNumber = digits.slice(6);
  return `(${area})-${prefix}-${lineNumber}`;
}

function formatPhoneNumberForInput(value = "") {
  const digits = stripPhoneNumber(value);
  if (digits.length === 0) return "";

  const area = digits.slice(0, 3);
  const prefix = digits.slice(3, 6);
  const lineNumber = digits.slice(6, 10);

  if (digits.length < 3) {
    return `(${area}`;
  }

  if (digits.length === 3) {
    return `(${area})`;
  }

  if (digits.length <= 6) {
    return `(${area})-${prefix}`;
  }

  return `(${area})-${prefix}-${lineNumber}`;
}

function normalizeMultiline(value = "") {
  return value
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter((line, index, arr) => line.length > 0 || index === arr.length - 1)
    .join("\n")
    .trim();
}

function normalizeProfileValues(values) {
  const phoneDigits = stripPhoneNumber(values.phone_number);

  return {
    company_name: values.company_name.trim(),
    contact_name: values.contact_name.trim(),
    contact_email: values.contact_email.trim().toLowerCase(),
    phone_number: phoneDigits,
    remit_to_address: normalizeMultiline(values.remit_to_address),
  };
}

function validateProfileValues(values) {
  if (values.company_name.length < 2) {
    return "Company name must be at least 2 characters.";
  }

  if (values.contact_name.length < 2 || !/^[\p{L} .'-]+$/u.test(values.contact_name)) {
    return "Enter a valid primary contact name.";
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.contact_email)) {
    return "Enter a valid primary contact email.";
  }

  if (values.phone_number.length !== PHONE_DIGIT_LENGTH) {
    return "Enter a 10-digit phone number in the format (###)-###-####.";
  }

  if (values.remit_to_address.length < 5) {
    return "Remit-to address must be at least 5 characters.";
  }

  return null;
}

function VendorProfileForm({
  initialValues,
  onSubmit,
  onCancel,
  saving,
  error,
  disableCancel,
}) {
  const [formValues, setFormValues] = useState({
    ...initialValues,
    phone_number: formatPhoneNumberForInput(initialValues.phone_number),
  });
  const [validationError, setValidationError] = useState(null);

  useEffect(() => {
    setFormValues({
      ...initialValues,
      phone_number: formatPhoneNumberForInput(initialValues.phone_number),
    });
    setValidationError(null);
  }, [initialValues]);

  function handleChange(event) {
    const { name, value } = event.target;
    if (name === "phone_number") {
      setFormValues((previous) => ({
        ...previous,
        [name]: formatPhoneNumberForInput(value),
      }));
      return;
    }

    setFormValues((previous) => ({ ...previous, [name]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const normalizedValues = normalizeProfileValues(formValues);
    const validationMessage = validateProfileValues(normalizedValues);

    if (validationMessage) {
      setValidationError(validationMessage);
      return;
    }

    setValidationError(null);
    onSubmit(normalizedValues);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4 py-6">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-900">Vendor profile</h2>
        <p className="mt-1 text-sm text-slate-600">
          We use this information on invoices and when we contact you about billing or
          support. Please keep it up to date.
        </p>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">
              Company name
              <input
                type="text"
                name="company_name"
                value={formValues.company_name}
                onChange={handleChange}
                required
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Primary contact name
              <input
                type="text"
                name="contact_name"
                value={formValues.contact_name}
                onChange={handleChange}
                required
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">
              Primary contact email
              <input
                type="email"
                name="contact_email"
                value={formValues.contact_email}
                onChange={handleChange}
                required
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Phone number
              <input
                type="tel"
                name="phone_number"
                value={formValues.phone_number}
                onChange={handleChange}
                required
                pattern={PHONE_INPUT_PATTERN.source}
                inputMode="tel"
                placeholder="(555)-123-4567"
                title="Enter a 10-digit phone number in the format (###)-###-####"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              />
            </label>
          </div>

          <label className="block text-sm font-medium text-slate-700">
            Remit-to address
            <textarea
              name="remit_to_address"
              value={formValues.remit_to_address}
              onChange={handleChange}
              required
              rows={4}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            />
          </label>

          {validationError ? (
            <p className="text-sm text-red-600">{validationError}</p>
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <div className="flex flex-wrap justify-end gap-3">
            {disableCancel ? null : (
              <button
                type="button"
                onClick={onCancel}
                disabled={saving}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Close
              </button>
            )}
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save details"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function VendorDashboard({ vendorId }) {
  const [jobs, setJobs] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [vendorProfile, setVendorProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileFormError, setProfileFormError] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [profilePromptDismissed, setProfilePromptDismissed] = useState(false);

  const { isAuthenticated, getAccessTokenSilently, loginWithRedirect } = useAuth0();

  const activeJobs = useMemo(
    () =>
      jobs.filter(
        (job) => job.status !== "completed" && job.status !== "skipped",
      ).length,
    [jobs],
  );

  const fetchJobs = useCallback(async () => {
    if (!isAuthenticated) return;

    setError(null);
    try {
      const token = await getAccessTokenSilently();
      const recentJobs = await listJobs(token);
      setJobs(recentJobs);
    } catch (err) {
      setError("Unable to load jobs");
    }
  }, [getAccessTokenSilently, isAuthenticated]);

  const loadVendorProfile = useCallback(async () => {
    if (!isAuthenticated || vendorId == null) {
      setVendorProfile(null);
      setProfileError(null);
      return null;
    }

    setProfileLoading(true);
    setProfileError(null);
    try {
      const token = await getAccessTokenSilently();
      const profile = await fetchVendorProfile(token);

      // 👇 Debug log to inspect the API data
      console.log("Vendor profile received:", profile);

      setVendorProfile(profile);
      return profile;
    } catch (err) {
      console.error("vendor_profile_fetch_failed", err);
      setVendorProfile(null);
      setProfileError(
        "We couldn't load your vendor profile. Refresh the page or try again later.",
      );
      return null;
    } finally {
      setProfileLoading(false);
    }
  }, [getAccessTokenSilently, isAuthenticated, vendorId]);

  useEffect(() => {
    if (!isAuthenticated) {
      setJobs([]);
      setError(null);
      setVendorProfile(null);
      setProfileError(null);
      setShowProfileForm(false);
      setProfilePromptDismissed(false);
      return;
    }

    fetchJobs();
    const timer = setInterval(fetchJobs, 5000);
    return () => clearInterval(timer);
  }, [fetchJobs, isAuthenticated]);

  useEffect(() => {
    loadVendorProfile();
  }, [loadVendorProfile]);

  useEffect(() => {
    setProfilePromptDismissed(false);
  }, [vendorId]);

  // 🔹 Updated logic – modal opens if missing company_name or incomplete or no profile at all
  useEffect(() => {
    if (
      !vendorProfile ||
      !vendorProfile.company_name ||
      !vendorProfile.is_profile_complete
    ) {
      if (!profilePromptDismissed) {
        setShowProfileForm(true);
      }
    }
  }, [vendorProfile, profilePromptDismissed]);

  async function handleProfileSubmit(updatedValues) {
    setProfileSaving(true);
    setProfileFormError(null);
    try {
      const token = await getAccessTokenSilently();
      const profile = await updateVendorProfile(token, updatedValues);
      setVendorProfile(profile);
      setShowProfileForm(false);
      setProfilePromptDismissed(false);
      toast.success("Vendor profile updated.");
    } catch (err) {
      console.error("vendor_profile_update_failed", err);
      setProfileFormError(
        err?.message ?? "We couldn't save your profile. Please try again.",
      );
    } finally {
      setProfileSaving(false);
    }
  }

  function handleProfileCancel() {
    setShowProfileForm(false);
    setProfilePromptDismissed(true);
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (vendorId == null) {
      setError(
        "Your account is not linked to a vendor profile yet. Please contact an administrator.",
      );
      event.target.value = "";
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      if (!isAuthenticated) {
        setError("Please log in to upload invoices.");
        await loginWithRedirect();
        return;
      }

      const token = await getAccessTokenSilently();
      const payload = {
        vendor_id: vendorId,
        invoice_date: new Date().toISOString().split("T")[0],
        service_month: new Date().toLocaleString("default", {
          month: "long",
          year: "numeric",
        }),
        invoice_code: `INV-${Date.now()}`,
      };
      await uploadInvoice(file, payload, token);
      await fetchJobs();
      toast.success("Upload received. We'll start processing right away.");
    } catch (err) {
      console.error("invoice_upload_failed", err);
      setError("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="space-y-4 text-sm text-slate-600">
        <p>Log in to submit invoices and track invoice processing jobs.</p>
        <button
          type="button"
          className="rounded bg-amber-500 px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600"
          onClick={() => loginWithRedirect()}
        >
          Log in with Auth0
        </button>
      </div>
    );
  }

  const initialProfileValues = {
    company_name: vendorProfile?.company_name ?? "",
    contact_name: vendorProfile?.contact_name ?? "",
    contact_email: vendorProfile?.contact_email ?? "",
    phone_number: formatPhoneNumberForDisplay(vendorProfile?.phone_number ?? ""),
    remit_to_address: vendorProfile?.remit_to_address ?? "",
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-slate-900">
                Vendor workspace
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                Upload timesheets, monitor invoice processing, and keep your contact
                information current so districts can reach you quickly.
              </p>
            </div>
            <div className="rounded-full bg-slate-100 px-4 py-1 text-sm font-medium text-slate-700">
              {activeJobs} {activeJobs === 1 ? "job" : "jobs"} in progress
            </div>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <aside className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Vendor profile</h2>
              {profileLoading ? (
                <p className="mt-3 text-sm text-slate-500">Loading profile…</p>
              ) : vendorProfile ? (
                <div className="mt-4 space-y-4 text-sm text-slate-600">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Company
                    </p>
                    <p className="mt-1 font-medium text-slate-900">
                      {vendorProfile.company_name || "Add company"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Primary contact
                    </p>
                    <p className="mt-1 font-medium text-slate-900">
                      {vendorProfile.contact_name || "Add a contact"}
                    </p>
                    <p>{vendorProfile.contact_email || "Add an email"}</p>
                    <p>
                      {vendorProfile.phone_number
                        ? formatPhoneNumberForDisplay(vendorProfile.phone_number)
                        : "Add a phone number"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Remit-to address
                    </p>
                    {vendorProfile.remit_to_address ? (
                      <address className="mt-1 whitespace-pre-line not-italic text-slate-900">
                        {vendorProfile.remit_to_address}
                      </address>
                    ) : (
                      <p>Add a remit-to address</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setShowProfileForm(true);
                      setProfilePromptDismissed(false);
                    }}
                    className="inline-flex items-center rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
                  >
                    Update profile
                  </button>
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">
                  Set up your vendor profile to get started.
                </p>
              )}
            </section>
          </aside>

          <main className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    Upload timesheets
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Upload a raw Excel timesheet to kick off automated invoice generation.
                    Status updates appear below within a few seconds of submission.
                  </p>
                </div>
                <label className="inline-flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-amber-400 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 shadow-sm transition hover:border-amber-500 hover:bg-amber-100">
                  <input
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={handleUpload}
                    disabled={isUploading}
                    className="sr-only"
                  />
                  {isUploading ? "Uploading…" : "Select file"}
                </label>
              </div>
              {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <h2 className="text-lg font-semibold text-slate-900">Recent activity</h2>
                <span className="text-sm text-slate-500">
                  {jobs.length} {jobs.length === 1 ? "submission" : "submissions"} tracked
                </span>
              </div>
              <div className="mt-4 space-y-3">
                {jobs.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No recent uploads. Submit your latest timesheet to generate a draft
                    invoice.
                  </p>
                ) : (
                  jobs.map((job) => <JobStatusCard key={job.id} job={job} />)
                )}
              </div>
            </section>
          </main>
        </section>
      </div>

      {showProfileForm ? (
        <VendorProfileForm
          initialValues={initialProfileValues}
          onSubmit={handleProfileSubmit}
          onCancel={handleProfileCancel}
          saving={profileSaving}
          error={profileFormError}
          disableCancel={!vendorProfile || !vendorProfile.is_profile_complete}
        />
      ) : null}
    </div>
  );
}
