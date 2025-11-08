import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";

import {
  fetchDistrictProfile,
  fetchDistrictVendors,
  updateDistrictProfile,
} from "../api/districts";

const menuItems = [
  {
    key: "vendors",
    label: "Vendors",
    description: "",
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

const MONTH_ORDER = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const MONTH_INDEX = MONTH_ORDER.reduce((acc, month, index) => {
  acc[month] = index;
  return acc;
}, {});

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const parseCurrencyValue = (value) => {
  if (!value || typeof value !== "string") {
    return 0;
  }

  const numeric = Number(value.replace(/[^0-9.-]+/g, ""));
  return Number.isFinite(numeric) ? numeric : 0;
};

const collectVendorInvoices = (profiles) =>
  profiles.flatMap((vendor) =>
    Object.entries(vendor.invoices ?? {}).flatMap(([yearString, invoices]) => {
      const year = Number(yearString);
      return (invoices ?? []).map((invoice) => {
        const monthIndex =
          typeof invoice.monthIndex === "number"
            ? invoice.monthIndex
            : MONTH_INDEX[invoice.month] ?? -1;
        const totalValue =
          typeof invoice.totalValue === "number"
            ? invoice.totalValue
            : parseCurrencyValue(invoice.total);

        return {
          vendorId: vendor.id,
          vendorName: vendor.name,
          year,
          month: invoice.month,
          monthIndex,
          status: invoice.status ?? "",
          total: totalValue,
        };
      });
    })
  );

const computeVendorMetrics = (profiles) => {
  const invoices = collectVendorInvoices(profiles);

  if (!invoices.length) {
    return {
      latestYear: null,
      totalVendors: profiles.length,
      invoicesThisYear: 0,
      approvedCount: 0,
      needsActionCount: 0,
      totalSpend: 0,
      outstandingSpend: 0,
    };
  }

  const latestYear = invoices.reduce((max, invoice) => (invoice.year > max ? invoice.year : max), invoices[0].year);
  const invoicesThisYear = invoices.filter((invoice) => invoice.year === latestYear);
  const approvedInvoices = invoicesThisYear.filter((invoice) => invoice.status.toLowerCase().includes("approved"));
  const needsActionInvoices = invoicesThisYear.filter((invoice) => !invoice.status.toLowerCase().includes("approved"));
  const totalSpend = invoicesThisYear.reduce((sum, invoice) => sum + invoice.total, 0);
  const outstandingSpend = needsActionInvoices.reduce((sum, invoice) => sum + invoice.total, 0);

  return {
    latestYear,
    totalVendors: profiles.length,
    invoicesThisYear: invoicesThisYear.length,
    approvedCount: approvedInvoices.length,
    needsActionCount: needsActionInvoices.length,
    totalSpend,
    outstandingSpend,
  };
};

const getLatestInvoiceForVendor = (vendor) => {
  const invoices = Object.entries(vendor.invoices ?? {}).flatMap(([yearString, entries]) => {
    const year = Number(yearString);
    return (entries ?? []).map((invoice) => ({
      ...invoice,
      year,
      monthIndex:
        typeof invoice.monthIndex === "number"
          ? invoice.monthIndex
          : MONTH_INDEX[invoice.month] ?? -1,
      totalValue:
        typeof invoice.totalValue === "number"
          ? invoice.totalValue
          : parseCurrencyValue(invoice.total),
    }));
  });

  if (!invoices.length) {
    return null;
  }

  return invoices.sort((a, b) => {
    if (a.year !== b.year) {
      return b.year - a.year;
    }
    return (b.monthIndex ?? -1) - (a.monthIndex ?? -1);
  })[0];
};

const getHealthBadgeClasses = (health) => {
  if (!health) {
    return "bg-slate-100 text-slate-600";
  }

  const normalized = health.toLowerCase();
  if (normalized.includes("track")) {
    return "bg-emerald-100 text-emerald-700";
  }
  if (normalized.includes("monitor")) {
    return "bg-amber-100 text-amber-700";
  }
  if (normalized.includes("procurement")) {
    return "bg-sky-100 text-sky-700";
  }
  return "bg-slate-100 text-slate-600";
};

const isApiError = (value) =>
  typeof value === "object" && value !== null && "status" in value;

function DistrictProfileForm({
  initialValues,
  onSubmit,
  onCancel,
  saving,
  error,
  disableCancel,
}) {
  const [formValues, setFormValues] = useState(initialValues);

  useEffect(() => {
    setFormValues(initialValues);
  }, [initialValues]);

  function handleChange(event) {
    const { name, value } = event.target;
    setFormValues((previous) => ({ ...previous, [name]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit({
      company_name: formValues.company_name.trim(),
      contact_name: formValues.contact_name.trim(),
      contact_email: formValues.contact_email.trim(),
      phone_number: formValues.phone_number.trim(),
      mailing_address: formValues.mailing_address.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4 py-6">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-900">District profile</h2>
        <p className="mt-1 text-sm text-slate-600">
          Keep your district contact information current so vendors and admins know how to reach you.
        </p>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">
              District name
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
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              />
            </label>
          </div>

          <label className="block text-sm font-medium text-slate-700">
            Mailing address
            <textarea
              name="mailing_address"
              value={formValues.mailing_address}
              onChange={handleChange}
              required
              rows={4}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            />
          </label>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              disabled={disableCancel || saving}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Close
            </button>
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


export default function DistrictDashboard({ districtId = null }) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  const [activeKey, setActiveKey] = useState(menuItems[0].key);
  const [selectedVendorId, setSelectedVendorId] = useState(null);
  const [selectedInvoiceKey, setSelectedInvoiceKey] = useState(null);
  const [vendorProfiles, setVendorProfiles] = useState([]);
  const [vendorsLoading, setVendorsLoading] = useState(false);
  const [vendorsError, setVendorsError] = useState(null);
  const [districtProfile, setDistrictProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileFormError, setProfileFormError] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [profilePromptDismissed, setProfilePromptDismissed] = useState(false);

  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];
  const selectedVendor = vendorProfiles.find((vendor) => vendor.id === selectedVendorId) ?? null;
  const vendorMetrics = useMemo(() => computeVendorMetrics(vendorProfiles), [vendorProfiles]);

  const normalizeVendorOverview = useCallback(
    (overview) => {
      if (!overview?.vendors?.length) {
        return [];
      }

      return overview.vendors.map((vendor) => {
        const invoicesByYear = Object.entries(vendor.invoices ?? {}).reduce(
          (acc, [yearKey, invoices]) => {
            const sortedInvoices = [...(invoices ?? [])]
              .map((invoice) => {
                const monthIndex =
                  typeof invoice.month_index === "number"
                    ? invoice.month_index
                    : MONTH_INDEX[invoice.month] ?? -1;
                const students = (invoice.students ?? []).map((student) => ({
                  id: `student-${student.id}`,
                  name: student.name,
                  service: student.service ?? null,
                  amount: currencyFormatter.format(student.amount ?? 0),
                  amountValue: student.amount ?? 0,
                  pdfUrl: student.pdf_url ?? null,
                  timesheetUrl: student.timesheet_url ?? null,
                }));
                return {
                  month: invoice.month,
                  monthIndex,
                  total: currencyFormatter.format(invoice.total ?? 0),
                  totalValue: invoice.total ?? 0,
                  status: invoice.status ? invoice.status.trim() : "",
                  processedOn: invoice.processed_on ?? "Processing",
                  pdfUrl: invoice.pdf_url ?? null,
                  timesheetCsvUrl: invoice.timesheet_csv_url ?? null,
                  students,
                };
              })
              .sort((a, b) => (b.monthIndex ?? -1) - (a.monthIndex ?? -1));
            acc[Number(yearKey)] = sortedInvoices;
            return acc;
          },
          {},
        );

        const metrics = vendor.metrics ?? {
          latest_year: null,
          invoices_this_year: 0,
          approved_count: 0,
          needs_action_count: 0,
          total_spend: 0,
          outstanding_spend: 0,
        };

        const healthLabel =
          vendor.health_label ??
          (metrics.needs_action_count > 0
            ? "Needs Attention"
            : metrics.invoices_this_year > 0
            ? "On Track"
            : "Onboarding");

        const latestInvoice = vendor.latest_invoice
          ? {
              month: vendor.latest_invoice.month,
              year: vendor.latest_invoice.year,
              total: currencyFormatter.format(vendor.latest_invoice.total ?? 0),
              totalValue: vendor.latest_invoice.total ?? 0,
              status: vendor.latest_invoice.status ?? "",
            }
          : null;

        const summary = latestInvoice
          ? `Latest invoice ${latestInvoice.month} ${latestInvoice.year} • ${latestInvoice.total}`
          : "No invoices submitted yet.";

        const metricsCamel = {
          latestYear: metrics.latest_year ?? null,
          invoicesThisYear: metrics.invoices_this_year ?? 0,
          approvedCount: metrics.approved_count ?? 0,
          needsActionCount: metrics.needs_action_count ?? 0,
          totalSpend: metrics.total_spend ?? 0,
          outstandingSpend: metrics.outstanding_spend ?? 0,
        };

        const remitToAddress = vendor.remit_to_address?.trim();

        return {
          id: String(vendor.id),
          name: vendor.name,
          manager: vendor.contact_name?.trim() ?? "",
          email: vendor.contact_email?.trim() ?? "",
          phone: vendor.phone_number?.trim() ?? "",
          summary,
          health: healthLabel,
          highlights: [],
          invoices: invoicesByYear,
          metrics: metricsCamel,
          tileMetrics: {
            invoicesThisYear: metricsCamel.invoicesThisYear,
            approvedCount: metricsCamel.approvedCount,
            needsActionCount: metricsCamel.needsActionCount,
            totalSpend: metricsCamel.totalSpend,
          },
          latestInvoice,
          remitToAddress: remitToAddress && remitToAddress.length ? remitToAddress : null,
        };
      });
    },
    [],
  );

  const loadVendors = useCallback(async () => {
    if (!isAuthenticated) {
      setVendorProfiles([]);
      setVendorsError(null);
      return;
    }

    setVendorsLoading(true);
    setVendorsError(null);
    try {
      const token = await getAccessTokenSilently();
      const overview = await fetchDistrictVendors(token);
      setVendorProfiles(normalizeVendorOverview(overview));
    } catch (error) {
      console.error("district_vendor_overview_failed", error);
      setVendorsError("We couldn't load vendor activity. Please try again.");
      setVendorProfiles([]);
    } finally {
      setVendorsLoading(false);
    }
  }, [getAccessTokenSilently, isAuthenticated, normalizeVendorOverview]);

  const loadDistrictProfile = useCallback(async () => {
    if (!isAuthenticated) {
      setDistrictProfile(null);
      setProfileError(null);
      return null;
    }

    if (districtId == null) {
      setDistrictProfile(null);
      setProfileError(
        "Your account is not linked to a district profile yet. Please contact an administrator.",
      );
      return null;
    }

    setProfileLoading(true);
    setProfileError(null);
    try {
      const token = await getAccessTokenSilently();
      const profile = await fetchDistrictProfile(token);
      setDistrictProfile(profile);
      return profile;
    } catch (error) {
      console.error("district_profile_fetch_failed", error);
      setDistrictProfile(null);
      if (isApiError(error) && error.status === 404) {
        setProfileError(
          "Your account is not linked to a district profile yet. Please contact an administrator.",
        );
        return null;
      }
      setProfileError(
        "We couldn't load your district profile. Refresh the page or try again later.",
      );
      return null;
    } finally {
      setProfileLoading(false);
    }
  }, [districtId, getAccessTokenSilently, isAuthenticated]);

  const handleProfileSubmit = useCallback(
    async (values) => {
      setProfileSaving(true);
      setProfileFormError(null);
      try {
        const token = await getAccessTokenSilently();
        const profile = await updateDistrictProfile(token, values);
        setDistrictProfile(profile);
        setShowProfileForm(false);
        setProfilePromptDismissed(false);
        toast.success("District profile updated.");
      } catch (error) {
        console.error("district_profile_update_failed", error);
        setProfileFormError(
          error instanceof Error && error.message
            ? error.message
            : "We couldn't save your profile. Please try again.",
        );
      } finally {
        setProfileSaving(false);
      }
    },
    [getAccessTokenSilently],
  );

  const handleProfileCancel = useCallback(() => {
    setShowProfileForm(false);
    setProfileFormError(null);
    setProfilePromptDismissed(true);
  }, []);

  const initialProfileValues = useMemo(
    () => ({
      company_name: districtProfile?.company_name ?? "",
      contact_name: districtProfile?.contact_name ?? "",
      contact_email: districtProfile?.contact_email ?? "",
      phone_number: districtProfile?.phone_number ?? "",
      mailing_address: districtProfile?.mailing_address ?? "",
    }),
    [
      districtProfile?.company_name,
      districtProfile?.contact_name,
      districtProfile?.contact_email,
      districtProfile?.phone_number,
      districtProfile?.mailing_address,
    ],
  );
  useEffect(() => {
    if (!isAuthenticated) {
      setVendorProfiles([]);
      setVendorsError(null);
      setDistrictProfile(null);
      setProfileError(null);
      setShowProfileForm(false);
      setProfilePromptDismissed(false);
      return;
    }

    loadVendors().catch(() => {});
    loadDistrictProfile().catch(() => {});
  }, [isAuthenticated, loadDistrictProfile, loadVendors]);

  useEffect(() => {
    setProfilePromptDismissed(false);
  }, [districtProfile?.id]);

  useEffect(() => {
    if (
      districtProfile &&
      !districtProfile.is_profile_complete &&
      !profilePromptDismissed
    ) {
      setShowProfileForm(true);
    }
  }, [districtProfile, profilePromptDismissed]);

  useEffect(() => {
    if (
      selectedVendorId !== null &&
      !vendorProfiles.some((vendor) => vendor.id === selectedVendorId)
    ) {
      setSelectedVendorId(null);
    }
  }, [selectedVendorId, vendorProfiles]);

  useEffect(() => {
    setSelectedInvoiceKey(null);
  }, [activeKey, selectedVendorId]);

  const activeInvoiceDetails = useMemo(() => {
    if (!selectedVendor || !selectedInvoiceKey) {
      return null;
    }

    const invoiceRecord =
      selectedVendor.invoices[selectedInvoiceKey.year]?.find(
        (invoice) => invoice.month === selectedInvoiceKey.month
      ) ?? null;

    if (!invoiceRecord) {
      return null;
    }

    const invoicePdfBase = invoiceRecord.pdfUrl ?? "";
    const invoiceTimesheetBase = invoiceRecord.timesheetCsvUrl ?? "";

    const studentsWithSamples = invoiceRecord.students?.map((entry) => ({
      ...entry,
      pdfUrl:
        entry.pdfUrl ??
        (invoicePdfBase ? `${invoicePdfBase.replace(/\.pdf$/, "")}/${entry.id}.pdf` : null),
      timesheetUrl:
        entry.timesheetUrl ??
        (invoiceTimesheetBase ? `${invoiceTimesheetBase.replace(/\.csv$/, "")}/${entry.id}.csv` : null),
    }));

    return {
      ...invoiceRecord,
      year: selectedInvoiceKey.year,
      students: studentsWithSamples ?? [],
    };
  }, [selectedInvoiceKey, selectedVendor]);

  const vendorOverviewHighlights = useMemo(() => {
    if (!selectedVendor) {
      return [];
    }

    const metrics = selectedVendor.metrics ?? {
      invoicesThisYear: 0,
      approvedCount: 0,
      needsActionCount: 0,
      totalSpend: 0,
      outstandingSpend: 0,
    };

    const highlights = [
      {
        label: "Invoices this year",
        value: metrics.invoicesThisYear ? metrics.invoicesThisYear.toString() : "0",
      },
      {
        label: "Approved",
        value: metrics.approvedCount ? metrics.approvedCount.toString() : "0",
      },
      {
        label: "Needs action",
        value: metrics.needsActionCount ? metrics.needsActionCount.toString() : "0",
      },
      {
        label: "Spend YTD",
        value: currencyFormatter.format(metrics.totalSpend ?? 0),
      },
    ];

    if (metrics.outstandingSpend) {
      highlights.push({
        label: "Outstanding",
        value: currencyFormatter.format(metrics.outstandingSpend),
      });
    }

    return highlights.filter((item) => item.value && item.value !== "0");
  }, [selectedVendor]);

  const vendorContactSummary = useMemo(() => {
    if (!selectedVendor) {
      return null;
    }

    const segments = [];
    if (selectedVendor.manager) {
      let primaryContact = `Primary contact: ${selectedVendor.manager}`;
      segments.push(primaryContact);
    }

    const contactDetails = [selectedVendor.email, selectedVendor.phone].filter(Boolean);
    if (contactDetails.length) {
      segments.push(contactDetails.join(" • "));
    }

    return segments.length ? segments.join(" • ") : null;
  }, [selectedVendor]);

  const vendorHeaderContactLine = useMemo(() => {
    if (!selectedVendor) {
      return null;
    }

    const segments = [selectedVendor.manager, selectedVendor.email, selectedVendor.phone]
      .map((value) => (value ? value.trim() : ""))
      .filter(Boolean);

    return segments.length ? segments.join(" • ") : null;
  }, [selectedVendor]);

  const vendorRemitTo = useMemo(() => {
    if (!selectedVendor?.remitToAddress) {
      return null;
    }

    const trimmed = selectedVendor.remitToAddress.trim();
    return trimmed.length ? trimmed : null;
  }, [selectedVendor]);

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
                        ? "bg-slate-200 text-slate-900 shadow-inner"
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

        {activeItem.description ? (
          <p className="mt-4 text-base leading-relaxed text-slate-600">
            {activeItem.description}
          </p>
        ) : null}

        {activeItem.key === "vendors" ? (
          <div className="mt-8 space-y-6">
            {profileError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                {profileError}
              </div>
            ) : null}

            {profileLoading && !districtProfile ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                Loading district profile…
              </div>
            ) : null}

            {districtProfile ? (
              <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h4 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
                      District profile
                    </h4>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {districtProfile.company_name}
                    </p>
                    <div className="mt-3 space-y-1 text-sm text-slate-600">
                      <p>
                        Primary contact:{" "}
                        <span className="font-medium text-slate-900">
                          {districtProfile.contact_name || "Add a contact name"}
                        </span>
                      </p>
                      <p>
                        {(districtProfile.contact_email || "Add an email") +
                          " • " +
                          (districtProfile.phone_number || "Add a phone number")}
                      </p>
                      {districtProfile.mailing_address ? (
                        <p className="whitespace-pre-line">
                          {districtProfile.mailing_address}
                        </p>
                      ) : (
                        <p>Add a mailing address</p>
                      )}
                      <div className="mt-4 rounded-xl border border-dashed border-amber-300 bg-amber-50 p-4 text-amber-800">
                        <p className="text-xs font-semibold uppercase tracking-widest text-amber-600">
                          District access key
                        </p>
                        <p className="mt-2 font-mono text-lg font-semibold text-amber-900">
                          {districtProfile.district_key}
                        </p>
                        <p className="mt-1 text-xs text-amber-700">
                          Share this key only with trusted vendors so their invoices route to your district.
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {!districtProfile.is_profile_complete ? (
                      <span className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                        Complete your profile
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => setShowProfileForm(true)}
                      disabled={profileLoading}
                      className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Update profile
                    </button>
                  </div>
                </div>
              </section>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Vendor Partners</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{vendorMetrics.totalVendors}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Active with invoices{vendorMetrics.latestYear ? ` in ${vendorMetrics.latestYear}` : ""}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Invoices Reviewed</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{vendorMetrics.invoicesThisYear}</p>
                <p className="mt-1 text-xs text-slate-500">{vendorMetrics.approvedCount} approved</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Needs Attention</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{vendorMetrics.needsActionCount}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {currencyFormatter.format(vendorMetrics.outstandingSpend)} outstanding
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Spend To Date</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">
                  {currencyFormatter.format(vendorMetrics.totalSpend)}
                </p>
                <p className="mt-1 text-xs text-slate-500">Across current-year invoices</p>
              </div>
            </div>
            {!selectedVendor ? (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                  Active Vendors
                </h4>
                <p className="text-xs text-slate-500">
                  Choose a partner to review their invoices this fiscal year.
                </p>
                {vendorsLoading ? (
                  <p className="text-sm text-slate-500">Loading vendor activity…</p>
                ) : vendorsError ? (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                    {vendorsError}
                  </div>
                ) : vendorProfiles.length === 0 ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                    No vendor activity has been recorded yet.
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {vendorProfiles.map((vendor) => (
                      <button
                        key={vendor.id}
                        onClick={() => setSelectedVendorId(vendor.id)}
                        className="flex h-full flex-col justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:border-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
                        type="button"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{vendor.name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              Contact: {vendor.manager || "Not provided"}
                            </p>
                          </div>
                          {vendor.health ? (
                            <span
                              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${getHealthBadgeClasses(
                                vendor.health
                              )}`}
                            >
                              {vendor.health}
                            </span>
                          ) : null}
                        </div>
                        {vendor.summary ? (
                          <p className="text-xs leading-relaxed text-slate-600">{vendor.summary}</p>
                        ) : null}
                        <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="font-semibold text-slate-900">{vendor.tileMetrics.invoicesThisYear}</p>
                            <p className="text-[0.65rem] uppercase tracking-widest text-slate-500">Invoices this year</p>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="font-semibold text-slate-900">{vendor.tileMetrics.approvedCount}</p>
                            <p className="text-[0.65rem] uppercase tracking-widest text-slate-500">Approved</p>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="font-semibold text-slate-900">
                              {currencyFormatter.format(vendor.tileMetrics.totalSpend ?? 0)}
                            </p>
                            <p className="text-[0.65rem] uppercase tracking-widest text-slate-500">Spend YTD</p>
                          </div>
                          {(() => {
                            const latestInvoice = vendor.latestInvoice ?? getLatestInvoiceForVendor(vendor);
                            if (!latestInvoice) {
                              return null;
                            }
                            return (
                              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                                <p className="font-semibold text-slate-900">{latestInvoice.total}</p>
                                <p className="text-[0.65rem] uppercase tracking-widest text-slate-500">
                                  Last invoice: {latestInvoice.month} {latestInvoice.year}
                                </p>
                              </div>
                            );
                          })()}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : activeInvoiceDetails ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <button
                    onClick={() => setSelectedInvoiceKey(null)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    type="button"
                  >
                    <span aria-hidden="true">←</span>
                    Back to {selectedVendor.name} months
                  </button>
                  <button
                    onClick={() => setSelectedVendorId(null)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    type="button"
                  >
                    Change vendor
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-amber-500">{selectedVendor.name}</p>
                    <h4 className="mt-1 text-2xl font-semibold text-slate-900">
                      {activeInvoiceDetails.month} {activeInvoiceDetails.year}
                    </h4>
                    <p className="mt-1 text-sm text-slate-500">
                      Status: {activeInvoiceDetails.status} · Processed {activeInvoiceDetails.processedOn}
                    </p>
                    {vendorHeaderContactLine ? (
                      <p className="text-xs text-slate-500">{vendorHeaderContactLine}</p>
                    ) : null}
                    {vendorRemitTo ? (
                      <p className="mt-2 text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">Remit to:</span>
                        <br />
                        <span className="whitespace-pre-line text-slate-700">{vendorRemitTo}</span>
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                    <span className="inline-flex items-center rounded-full bg-slate-900 px-3 py-1 text-sm font-semibold text-white">
                      Total {activeInvoiceDetails.total}
                    </span>
                    {activeInvoiceDetails.pdfUrl ? (
                      <a
                        href={activeInvoiceDetails.pdfUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center rounded-full bg-amber-500 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                      >
                        Download PDF Invoice
                      </a>
                    ) : (
                      <span className="text-xs text-slate-500">
                        Invoice file not available
                      </span>
                    )}
                  </div>
                </div>

                {vendorOverviewHighlights.length ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                        Partner Snapshot
                      </p>
                      {selectedVendor.health ? (
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${getHealthBadgeClasses(
                            selectedVendor.health
                          )}`}
                        >
                          {selectedVendor.health}
                        </span>
                      ) : null}
                    </div>
                    {selectedVendor.summary ? (
                      <p className="mt-3 text-sm leading-relaxed text-slate-600">{selectedVendor.summary}</p>
                    ) : null}
                    <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                      {vendorOverviewHighlights.map((item) => (
                        <div
                          key={`${item.label}-${item.value}`}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm"
                        >
                          <dt className="text-[0.65rem] uppercase tracking-widest text-slate-500">{item.label}</dt>
                          <dd className="mt-1 text-sm font-semibold text-slate-900">{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                    {vendorContactSummary ? (
                      <p className="mt-4 text-xs text-slate-500">{vendorContactSummary}</p>
                    ) : null}
                    {vendorRemitTo ? (
                      <p className="mt-3 text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">Remit to:</span>
                        <br />
                        <span className="whitespace-pre-line text-slate-700">{vendorRemitTo}</span>
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <div className="space-y-3">
                  <h5 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Student services</h5>
                  {activeInvoiceDetails.students?.length ? (
                    <ul className="space-y-3">
                      {activeInvoiceDetails.students.map((entry) => {
                        const invoicePdfBase = activeInvoiceDetails.pdfUrl ?? "";
                        const invoiceTimesheetBase = activeInvoiceDetails.timesheetCsvUrl ?? "";
                        const studentInvoiceUrl = entry.pdfUrl
                          ? entry.pdfUrl
                          : invoicePdfBase
                          ? `${invoicePdfBase.replace(/\.pdf$/, "")}/${entry.id}.pdf`
                          : null;
                        const studentTimesheetUrl = entry.timesheetUrl
                          ? entry.timesheetUrl
                          : invoiceTimesheetBase
                          ? `${invoiceTimesheetBase.replace(/\.csv$/, "")}/${entry.id}.csv`
                          : null;

                        return (
                          <li
                            key={entry.id}
                            className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                          >
                            <div className="flex flex-col gap-2 text-sm text-slate-700 sm:flex-row sm:items-start sm:justify-between">
                              <p className="text-sm text-slate-700">
                                <span className="font-semibold text-slate-900">
                                  Student Name: {entry.name}
                                </span>
                                {entry.service ? <span>, Service: {entry.service}</span> : null}
                              </p>
                              <div className="flex flex-wrap items-center gap-2 sm:ml-6 sm:self-start">
                                {entry.amount ? (
                                  <span className="font-semibold text-slate-900">{entry.amount}</span>
                                ) : null}
                                {studentInvoiceUrl ? (
                                  <a
                                    href={studentInvoiceUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 transition hover:bg-amber-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                                  >
                                    PDF Invoice
                                  </a>
                                ) : null}
                                {studentTimesheetUrl ? (
                                  <a
                                    href={studentTimesheetUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                                  >
                                    Timesheet CSV
                                  </a>
                                ) : null}
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="text-sm text-slate-500">No student services were reported for this month.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-amber-500">{selectedVendor.name}</p>
                    <h4 className="mt-1 text-2xl font-semibold text-slate-900">Select a month</h4>
                    <p className="mt-1 text-sm text-slate-500">Choose a billing month to review detailed student services.</p>
                    {vendorHeaderContactLine ? (
                      <p className="mt-2 text-xs text-slate-500">{vendorHeaderContactLine}</p>
                    ) : null}
                    {vendorRemitTo ? (
                      <p className="mt-2 text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">Remit to:</span>
                        <br />
                        <span className="whitespace-pre-line text-slate-700">{vendorRemitTo}</span>
                      </p>
                    ) : null}
                  </div>
                  <button
                    onClick={() => setSelectedVendorId(null)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    type="button"
                  >
                    <span aria-hidden="true">←</span>
                    Back to vendors
                  </button>
                </div>

                {vendorOverviewHighlights.length ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                        Partner Snapshot
                      </p>
                      {selectedVendor.health ? (
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${getHealthBadgeClasses(
                            selectedVendor.health
                          )}`}
                        >
                          {selectedVendor.health}
                        </span>
                      ) : null}
                    </div>
                    {selectedVendor.summary ? (
                      <p className="mt-3 text-sm leading-relaxed text-slate-600">{selectedVendor.summary}</p>
                    ) : null}
                    <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                      {vendorOverviewHighlights.map((item) => (
                        <div
                          key={`${item.label}-${item.value}`}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm"
                        >
                          <dt className="text-[0.65rem] uppercase tracking-widest text-slate-500">{item.label}</dt>
                          <dd className="mt-1 text-sm font-semibold text-slate-900">{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                    {vendorContactSummary ? (
                      <p className="mt-4 text-xs text-slate-500">{vendorContactSummary}</p>
                    ) : null}
                    {vendorRemitTo ? (
                      <p className="mt-3 text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">Remit to:</span>
                        <br />
                        <span className="whitespace-pre-line text-slate-700">{vendorRemitTo}</span>
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <div className="space-y-6">
                  {Object.entries(selectedVendor.invoices)
                    .sort(([yearA], [yearB]) => Number(yearB) - Number(yearA))
                    .map(([year, invoices]) => (
                      <div key={year} className="space-y-3">
                        <h5 className="text-sm font-semibold uppercase tracking-wider text-slate-500">{year}</h5>
                        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                          {invoices.map((invoice) => (
                            <button
                              key={`${year}-${invoice.month}`}
                              onClick={() =>
                                setSelectedInvoiceKey({
                                  month: invoice.month,
                                  year: Number(year),
                                })
                              }
                              className="flex h-full flex-col justify-center rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:border-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
                              type="button"
                            >
                              <p className="text-lg font-semibold text-slate-900">
                                {`${invoice.month} - ${invoice.total}`}
                              </p>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
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

      {showProfileForm ? (
        <DistrictProfileForm
          initialValues={initialProfileValues}
          onSubmit={handleProfileSubmit}
          onCancel={handleProfileCancel}
          saving={profileSaving}
          error={profileFormError}
          disableCancel={profileSaving}
        />
      ) : null}
    </div>
  );
}
