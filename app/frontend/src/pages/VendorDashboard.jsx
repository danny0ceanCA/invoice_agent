import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import { uploadInvoice } from "../api/invoices";
import { listJobs } from "../api/jobs";
import {
  fetchVendorProfile,
  updateVendorProfile,
} from "../api/vendors";
import { formatPostalAddress } from "../api/common";
import JobStatusCard from "./JobStatusCard";
import VendorProfileWizard from "../components/VendorProfileWizard";

const PHONE_DIGIT_LENGTH = 10;
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

export default function VendorDashboard({ vendorId }) {
  const [jobs, setJobs] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [vendorProfile, setVendorProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [isWizardManuallyOpened, setIsWizardManuallyOpened] = useState(false);

  const { isAuthenticated, getAccessTokenSilently, loginWithRedirect } = useAuth0();
  const navigate = useNavigate();

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
      setIsWizardManuallyOpened(false);
      return;
    }

    fetchJobs();
    const timer = setInterval(fetchJobs, 5000);
    return () => clearInterval(timer);
  }, [fetchJobs, isAuthenticated]);

  useEffect(() => {
    loadVendorProfile();
  }, [loadVendorProfile]);

  // 🔹 Updated logic – wizard opens if missing company_name or incomplete or no profile at all
  useEffect(() => {
    if (
      !vendorProfile ||
      !vendorProfile.company_name ||
      !vendorProfile.is_profile_complete
    ) {
      setShowProfileForm(true);
      setIsWizardManuallyOpened(false);
      return;
    }
    if (!isWizardManuallyOpened) {
      setShowProfileForm(false);
    }
  }, [isWizardManuallyOpened, vendorProfile]);

  async function handleProfileSubmit(updatedValues) {
    try {
      const token = await getAccessTokenSilently();
      const profile = await updateVendorProfile(token, updatedValues);
      setVendorProfile(profile);
      toast.success("Vendor profile updated.");
      return profile;
    } catch (err) {
      console.error("vendor_profile_update_failed", err);
      const message =
        err?.message ?? "We couldn't save your profile. Please try again.";
      throw new Error(message);
    }
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

    if (!vendorProfile?.is_district_linked) {
      setError(
        "Connect to your district using the district access key before submitting invoices.",
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

  const initialProfileValues = useMemo(
    () => ({
      company_name: vendorProfile?.company_name ?? "",
      contact_name: vendorProfile?.contact_name ?? "",
      contact_email: vendorProfile?.contact_email ?? "",
      phone_number: formatPhoneNumberForDisplay(
        vendorProfile?.phone_number ?? "",
      ),
      remit_to_address: {
        street: vendorProfile?.remit_to_address?.street ?? "",
        city: vendorProfile?.remit_to_address?.city ?? "",
        state: vendorProfile?.remit_to_address?.state ?? "",
        postal_code: vendorProfile?.remit_to_address?.postal_code ?? "",
      },
    }),
    [
      vendorProfile?.company_name,
      vendorProfile?.contact_name,
      vendorProfile?.contact_email,
      vendorProfile?.phone_number,
      vendorProfile?.remit_to_address?.street,
      vendorProfile?.remit_to_address?.city,
      vendorProfile?.remit_to_address?.state,
      vendorProfile?.remit_to_address?.postal_code,
    ],
  );

  const formattedRemitAddress = useMemo(
    () => formatPostalAddress(vendorProfile?.remit_to_address ?? null),
    [
      vendorProfile?.remit_to_address?.street,
      vendorProfile?.remit_to_address?.city,
      vendorProfile?.remit_to_address?.state,
      vendorProfile?.remit_to_address?.postal_code,
    ],
  );

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
              {profileError ? (
                <p className="mt-3 text-sm text-red-600">{profileError}</p>
              ) : profileLoading ? (
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
                    {formattedRemitAddress ? (
                      <address className="mt-1 whitespace-pre-line not-italic text-slate-900">
                        {formattedRemitAddress}
                      </address>
                    ) : (
                      <p>Add a remit-to address</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setIsWizardManuallyOpened(true);
                      setShowProfileForm(true);
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
            <section className="grid gap-4 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => navigate("/vendor/district-keys")}
                className="flex h-full w-full flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-amber-400 hover:shadow-md"
              >
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">District keys</h2>
                  <p className="mt-2 text-sm text-slate-600">
                    Manage the access keys that connect your organization to partner districts.
                  </p>
                </div>
                <span className="mt-4 text-xs font-semibold uppercase tracking-wide text-amber-600">
                  Manage access
                </span>
              </button>
            </section>
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
        <VendorProfileWizard
          initialValues={initialProfileValues}
          onSubmit={handleProfileSubmit}
          onClose={() => {
            setShowProfileForm(false);
            setIsWizardManuallyOpened(false);
          }}
        />
      ) : null}
    </div>
  );
}
