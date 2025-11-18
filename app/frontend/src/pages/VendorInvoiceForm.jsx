import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import { uploadInvoice } from "../api/invoices";
import { fetchVendorProfile } from "../api/vendors";

export default function VendorInvoiceForm({ vendorId }) {
  const [pendingFile, setPendingFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [serviceMonth, setServiceMonth] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [error, setError] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);

  const fileInputRef = useRef(null);
  const navigate = useNavigate();
  const { isAuthenticated, getAccessTokenSilently, loginWithRedirect } =
    useAuth0();

  const serviceMonthOptions = useMemo(() => {
    const now = new Date();

    return Array.from({ length: 12 }, (_, index) => {
      const date = new Date(now.getFullYear(), now.getMonth() - index, 1);
      const value = date.toLocaleString("default", {
        month: "long",
        year: "numeric",
      });

      return { value, label: value };
    });
  }, []);

  useEffect(() => {
    if (serviceMonthOptions.length > 0 && !serviceMonth) {
      setServiceMonth(serviceMonthOptions[0].value);
    }
  }, [serviceMonthOptions, serviceMonth]);

  const loadProfile = useCallback(async () => {
    if (!isAuthenticated || vendorId == null) {
      setProfileError(
        "Your account is not linked to a vendor profile yet. Please contact an administrator.",
      );
      return null;
    }

    setProfileLoading(true);
    setProfileError(null);
    try {
      const token = await getAccessTokenSilently();
      const profile = await fetchVendorProfile(token);

      if (!profile.is_district_linked) {
        setProfileError(
          "Connect to your district using the district access key before submitting invoices.",
        );
      }

      return profile;
    } catch (err) {
      console.error("vendor_profile_fetch_failed", err);
      setProfileError(
        "We couldn't load your vendor profile. Refresh the page or try again later.",
      );
      return null;
    } finally {
      setProfileLoading(false);
    }
  }, [getAccessTokenSilently, isAuthenticated, vendorId]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleFileSelection = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setPendingFile(file);
    setError(null);
  };

  async function submitUpload(event) {
    event.preventDefault();
    setError(null);

    if (vendorId == null) {
      setError(
        "Your account is not linked to a vendor profile yet. Please contact an administrator.",
      );
      return;
    }

    if (!isAuthenticated) {
      setError("Please log in to upload invoices.");
      await loginWithRedirect();
      return;
    }

    if (profileError) {
      setError(profileError);
      return;
    }

    if (!pendingFile) {
      setError("Please select a timesheet file to upload.");
      return;
    }

    if (!invoiceDate) {
      setError("Please choose an invoice date.");
      return;
    }

    if (new Date(invoiceDate) > new Date()) {
      setError("Invoice date cannot be in the future.");
      return;
    }

    setIsUploading(true);

    try {
      const token = await getAccessTokenSilently();
      const payload = {
        vendor_id: vendorId,
        invoice_date: invoiceDate,
        service_month: serviceMonth,
        invoice_code: `INV-${Date.now()}`,
      };

      await uploadInvoice(pendingFile, payload, token);
      toast.success("Upload received. We'll start processing right away.");
      navigate("/");
    } catch (err) {
      console.error("invoice_upload_failed", err);
      setError("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm font-semibold uppercase tracking-wide text-amber-600">
              Generate invoice
            </p>
            <h1 className="text-2xl font-semibold text-slate-900">Add invoice details</h1>
            <p className="text-sm text-slate-600">
              Choose the service month and invoice date before uploading your timesheet.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/")}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
          >
            Back to workspace
          </button>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <form className="space-y-5" onSubmit={submitUpload}>
            <div>
              <label className="text-sm font-medium text-slate-900">Service month</label>
              <p className="text-xs text-slate-500">
                Select the month the services were delivered.
              </p>
              <select
                className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                value={serviceMonth}
                onChange={(event) => setServiceMonth(event.target.value)}
                required
              >
                {serviceMonthOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-900">Invoice date</label>
              <p className="text-xs text-slate-500">Must be today or earlier.</p>
              <input
                type="date"
                max={new Date().toISOString().split("T")[0]}
                value={invoiceDate}
                onChange={(event) => setInvoiceDate(event.target.value)}
                className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                required
              />
            </div>

            <div>
              <label className="text-sm font-medium text-slate-900">Timesheet file</label>
              <p className="text-xs text-slate-500">Select a .xlsx or .xls file to upload.</p>
              <div className="mt-2 flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleFileSelection}
                  className="sr-only"
                  aria-label="Select timesheet file"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-100"
                  disabled={isUploading}
                >
                  Choose file
                </button>
                <span className="text-sm text-slate-600">
                  {pendingFile ? pendingFile.name : "No file chosen"}
                </span>
              </div>
            </div>

            {profileLoading ? (
              <p className="text-sm text-slate-500">Checking your vendor profile…</p>
            ) : profileError ? (
              <p className="text-sm text-red-600">{profileError}</p>
            ) : null}

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => navigate("/")}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
                disabled={isUploading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-70"
                disabled={isUploading}
              >
                {isUploading ? "Uploading…" : "Upload timesheet"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
