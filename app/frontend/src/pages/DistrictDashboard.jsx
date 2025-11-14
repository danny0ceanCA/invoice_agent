import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import ChatAgent from "../components/ChatAgent.jsx";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";
import { CheckCircle2, Plus } from "lucide-react";

import {
  fetchDistrictProfile,
  fetchDistrictVendors,
  fetchDistrictMemberships,
  updateDistrictProfile,
  addDistrictMembership,
  activateDistrictMembership,
} from "../api/districts";
import { formatPostalAddress } from "../api/common";
import {
  fetchInvoicePresignedUrl,
  fetchVendorInvoiceArchive,
  fetchVendorInvoicesForMonth,
} from "../api/invoices";

const menuItems = [
  {
    key: "vendors",
    label: "Vendors",
    description: null,
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
    route: "/analytics",
    description:
      "Dive into spending trends, utilization rates, and budget insights. Ask questions using the AI Analytics Assistant to generate reports instantly.",
  },
  {
    key: "settings",
    label: "Settings",
    description:
      "Configure district preferences, manage your profile, and maintain console access keys.",
    comingSoon: false,
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

const MONTH_NAME_LOOKUP = Object.entries(MONTH_INDEX).reduce(
  (acc, [name, index]) => {
    acc[name.toLowerCase()] = index;
    return acc;
  },
  {},
);

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const parseCurrencyValue = (value) => {
  if (!value) {
    return 0;
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value !== "string") {
    return 0;
  }

  const numeric = Number(value.replace(/[^0-9.-]+/g, ""));
  return Number.isFinite(numeric) ? numeric : 0;
};

const resolveMonthNumber = (monthName, monthIndex) => {
  if (typeof monthIndex === "number" && monthIndex >= 0) {
    return monthIndex + 1;
  }

  if (typeof monthName === "number" && monthName >= 1 && monthName <= 12) {
    return monthName;
  }

  if (typeof monthName !== "string") {
    return null;
  }

  const trimmed = monthName.trim();
  if (!trimmed) {
    return null;
  }

  const numeric = Number.parseInt(trimmed, 10);
  if (Number.isFinite(numeric) && numeric >= 1 && numeric <= 12) {
    return numeric;
  }

  const lookup = MONTH_NAME_LOOKUP[trimmed.toLowerCase()];
  if (typeof lookup === "number") {
    return lookup + 1;
  }

  return null;
};

const formatDisplayDateTime = (value) => {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const formatInvoiceDisplayName = (value) => {
  if (typeof value !== "string" || !value.trim()) {
    return value;
  }

  const cleanName = value
    .replace(/^Invoice_/, "")
    .replace(/_[0-9a-f]{32}\.pdf$/i, "")
    .replace(/\.pdf$/i, "");

  const parts = cleanName.split("_");
  if (parts.length > 2 && parts[0].length > 1) {
    const [firstName, lastName, ...rest] = parts;
    const compressedName = lastName ? `${firstName[0]}${lastName}` : firstName[0];
    return [compressedName, ...rest].join("_");
  }

  return parts.join("_");
};

const sanitizeFilenameSegment = (value) => {
  if (!value) {
    return "file";
  }

  return value
    .toString()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "file";
};

const aggregateStudentEntries = (entries) => {
  if (!Array.isArray(entries) || !entries.length) {
    return [];
  }

  const groups = new Map();

  entries.forEach((entry, index) => {
    const normalizedStudentKey =
      typeof entry.studentKey === "string" && entry.studentKey.trim().length
        ? entry.studentKey.trim()
        : null;
    const normalizedId =
      typeof entry.studentId === "string" && entry.studentId.trim().length
        ? entry.studentId.trim()
        : null;
    const fallbackOriginalStudentId =
      typeof entry.originalStudentId === "string" && entry.originalStudentId.trim().length
        ? entry.originalStudentId.trim()
        : null;
    const fallbackEntryId =
      typeof entry.id === "string" && entry.id.trim().length
        ? entry.id.trim()
        : null;
    const fallbackLineItemId =
      typeof entry.originalLineItemId === "string" && entry.originalLineItemId.trim().length
        ? entry.originalLineItemId.trim()
        : entry.originalLineItemId ?? null;

    const key =
      normalizedId ??
      fallbackOriginalStudentId ??
      fallbackEntryId ??
      fallbackLineItemId ??
      normalizedStudentKey ??
      `${entry.name || "unknown"}-${index}`;

    const amountValue =
      typeof entry.amountValue === "number"
        ? entry.amountValue
        : parseCurrencyValue(entry.amount ?? "");

    const displayName =
      typeof entry.name === "string" && entry.name.trim().length
        ? entry.name.trim()
        : "Unknown student";

    if (!groups.has(key)) {
      groups.set(key, {
        id: normalizedId ?? fallbackEntryId ?? key,
        studentKey: normalizedStudentKey,
        name: displayName,
        amountValue: 0,
        services: new Map(),
        pdfUrls: new Set(),
        pdfKeys: new Set(),
        timesheetUrls: new Set(),
        originalLineItemIds: new Set(),
        entryCount: 0,
      });
    }

    const group = groups.get(key);
    if (!group.name && displayName) {
      group.name = displayName;
    }
    group.amountValue += amountValue;
    group.entryCount += 1;

    const serviceKey = entry.service?.trim();
    if (serviceKey) {
      const current = group.services.get(serviceKey) ?? { count: 0, amount: 0 };
      current.count += 1;
      current.amount += amountValue;
      group.services.set(serviceKey, current);
    }

    if (entry.pdfUrl) group.pdfUrls.add(entry.pdfUrl);
    if (entry.pdfS3Key) group.pdfKeys.add(entry.pdfS3Key);
    if (entry.timesheetUrl) group.timesheetUrls.add(entry.timesheetUrl);
    if (entry.originalLineItemId != null) {
      group.originalLineItemIds.add(entry.originalLineItemId);
    }
  });

  return Array.from(groups.values())
    .map((group) => {
      const services = Array.from(group.services.entries()).map(
        ([service, data]) => ({
          service,
          count: data.count,
          amount: data.amount,
        })
      );

      const pdfUrls = Array.from(group.pdfUrls);
      const pdfKeys = Array.from(group.pdfKeys);
      const timesheetUrls = Array.from(group.timesheetUrls);
      const originalLineItemIds = Array.from(group.originalLineItemIds);

      return {
        id: group.id,
        studentKey: group.studentKey ?? null,
        name: group.name,
        amountValue: group.amountValue,
        amount: currencyFormatter.format(group.amountValue ?? 0),
        services: services.map((item) => item.service),
        serviceBreakdown: services,
        serviceSummary:
          services.length === 1
            ? services[0].service
            : services.length > 1
            ? `${services.length} services`
            : null,
        pdfUrl: pdfUrls[0] ?? null,
        pdfS3Key: pdfKeys[0] ?? null,
        timesheetUrl: timesheetUrls[0] ?? null,
        originalLineItemId: originalLineItemIds[0] ?? null,
        entryCount: group.entryCount,
      };
    })
    .sort((a, b) => {
      if (b.amountValue !== a.amountValue) return b.amountValue - a.amountValue;
      return a.name.localeCompare(b.name);
    });
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

const isEmailLike = (value) =>
  typeof value === "string" && value.trim().includes("@") && value.trim().includes(".");

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
  const hasProfileData = useMemo(() => {
    const fields = [
      initialValues.company_name,
      initialValues.contact_name,
      initialValues.contact_email,
      initialValues.phone_number,
      initialValues.mailing_address?.street,
      initialValues.mailing_address?.city,
      initialValues.mailing_address?.state,
      initialValues.mailing_address?.postal_code,
    ];
    return fields.some((value) =>
      typeof value === "string" ? value.trim().length > 0 : Boolean(value),
    );
  }, [
    initialValues.company_name,
    initialValues.contact_name,
    initialValues.contact_email,
    initialValues.phone_number,
    initialValues.mailing_address?.street,
    initialValues.mailing_address?.city,
    initialValues.mailing_address?.state,
    initialValues.mailing_address?.postal_code,
  ]);
  const [isEditing, setIsEditing] = useState(() => !hasProfileData);
  const [formValues, setFormValues] = useState(() => ({
    ...initialValues,
    mailing_address: {
      street: initialValues.mailing_address?.street ?? "",
      city: initialValues.mailing_address?.city ?? "",
      state: initialValues.mailing_address?.state ?? "",
      postal_code: initialValues.mailing_address?.postal_code ?? "",
    },
  }));

  useEffect(() => {
    setFormValues({
      ...initialValues,
      mailing_address: {
        street: initialValues.mailing_address?.street ?? "",
        city: initialValues.mailing_address?.city ?? "",
        state: initialValues.mailing_address?.state ?? "",
        postal_code: initialValues.mailing_address?.postal_code ?? "",
      },
    });
  }, [initialValues]);

  useEffect(() => {
    if (!hasProfileData) {
      setIsEditing(true);
    }
  }, [hasProfileData]);

  const displayMailingAddress = useMemo(
    () => formatPostalAddress(initialValues.mailing_address ?? null),
    [
      initialValues.mailing_address?.street,
      initialValues.mailing_address?.city,
      initialValues.mailing_address?.state,
      initialValues.mailing_address?.postal_code,
    ],
  );

  function handleChange(event) {
    const { name, value } = event.target;
    if (name.startsWith("mailing_address.")) {
      const [, field] = name.split(".");
      setFormValues((previous) => ({
        ...previous,
        mailing_address: {
          ...previous.mailing_address,
          [field]: value,
        },
      }));
      return;
    }

    setFormValues((previous) => ({ ...previous, [name]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit({
      company_name: formValues.company_name.trim(),
      contact_name: formValues.contact_name.trim(),
      contact_email: formValues.contact_email.trim(),
      phone_number: formValues.phone_number.trim(),
      mailing_address: {
        street: formValues.mailing_address?.street?.trim() ?? "",
        city: formValues.mailing_address?.city?.trim() ?? "",
        state: formValues.mailing_address?.state?.trim().toUpperCase() ?? "",
        postal_code: formValues.mailing_address?.postal_code?.trim() ?? "",
      },
    });
  }

  function handleStartEditing() {
    setFormValues(initialValues);
    setIsEditing(true);
  }

  function handleCancelEditing() {
    setFormValues(initialValues);
    setIsEditing(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4 py-6">
      <div className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">District profile</h2>
            <p className="mt-1 text-sm text-slate-600">
              Keep your district contact information current so vendors and admins know how to reach you.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={disableCancel || saving}
            className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Close
          </button>
        </div>

        {isEditing ? (
          <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-company-name">
                  District name
                </label>
                <input
                  id="district-profile-company-name"
                  type="text"
                  name="company_name"
                  value={formValues.company_name}
                  onChange={handleChange}
                  required
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-contact-name">
                  Primary contact name
                </label>
                <input
                  id="district-profile-contact-name"
                  type="text"
                  name="contact_name"
                  value={formValues.contact_name}
                  onChange={handleChange}
                  required
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-contact-email">
                  Primary contact email
                </label>
                <input
                  id="district-profile-contact-email"
                  type="email"
                  name="contact_email"
                  value={formValues.contact_email}
                  onChange={handleChange}
                  required
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-phone-number">
                  Phone number
                </label>
                <input
                  id="district-profile-phone-number"
                  type="tel"
                  name="phone_number"
                  value={formValues.phone_number}
                  onChange={handleChange}
                  required
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-mailing-street">
                  Mailing street
                </label>
                <input
                  id="district-profile-mailing-street"
                  type="text"
                  name="mailing_address.street"
                  value={formValues.mailing_address.street}
                  onChange={handleChange}
                  required
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-mailing-city">
                    City
                  </label>
                  <input
                    id="district-profile-mailing-city"
                    type="text"
                    name="mailing_address.city"
                    value={formValues.mailing_address.city}
                    onChange={handleChange}
                    required
                    className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-mailing-state">
                    State
                  </label>
                  <input
                    id="district-profile-mailing-state"
                    type="text"
                    name="mailing_address.state"
                    value={formValues.mailing_address.state}
                    onChange={handleChange}
                    required
                    maxLength={2}
                    className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm uppercase text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700" htmlFor="district-profile-mailing-postal">
                    ZIP code
                  </label>
                  <input
                    id="district-profile-mailing-postal"
                    type="text"
                    name="mailing_address.postal_code"
                    value={formValues.mailing_address.postal_code}
                    onChange={handleChange}
                    required
                    className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
                  />
                </div>
              </div>
            </div>

            {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}

            <div className="flex flex-wrap justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelEditing}
                disabled={saving}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
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
        ) : (
          <div className="mt-6 space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">District name</p>
                <p className="mt-2 text-sm font-medium text-slate-900">
                  {initialValues.company_name ? (
                    initialValues.company_name
                  ) : (
                    <span className="font-normal text-slate-400">Add a district name</span>
                  )}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Primary contact</p>
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  <p className="font-medium text-slate-900">
                    {initialValues.contact_name ? (
                      initialValues.contact_name
                    ) : (
                      <span className="font-normal text-slate-400">Add a contact name</span>
                    )}
                  </p>
                  <p>
                    {initialValues.contact_email ? (
                      <span className="text-slate-700">{initialValues.contact_email}</span>
                    ) : (
                      <span className="text-slate-400">Add an email</span>
                    )}
                  </p>
                  <p>
                    {initialValues.phone_number ? (
                      <span className="text-slate-700">{initialValues.phone_number}</span>
                    ) : (
                      <span className="text-slate-400">Add a phone number</span>
                    )}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Mailing address</p>
              <p className="mt-2 whitespace-pre-line text-sm text-slate-700">
                {displayMailingAddress ? (
                  displayMailingAddress
                ) : (
                  <span className="text-slate-400">Add a mailing address</span>
                )}
              </p>
            </div>

            <div className="flex flex-wrap justify-end gap-3">
              <button
                type="button"
                onClick={handleStartEditing}
                className="inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
              >
                Edit profile
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


export default function DistrictDashboard({
  districtId = null,
  initialMemberships = [],
  onMembershipChange = null,
  initialActiveKey = null,
}) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  const location = useLocation();
  const navigate = useNavigate();
  const [activeKey, setActiveKey] = useState(
    initialActiveKey && menuItems.some((m) => m.key === initialActiveKey)
      ? initialActiveKey
      : menuItems[0].key
  );
  const [selectedVendorId, setSelectedVendorId] = useState(null);
  const [selectedInvoiceKey, setSelectedInvoiceKey] = useState(null);
  const [vendorProfiles, setVendorProfiles] = useState([]);
  const [vendorsLoading, setVendorsLoading] = useState(false);
  const [vendorsError, setVendorsError] = useState(null);
  const [activeInvoiceDetails, setActiveInvoiceDetails] = useState(null);
  const [districtProfile, setDistrictProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileFormError, setProfileFormError] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [memberships, setMemberships] = useState(initialMemberships);
  const [membershipLoading, setMembershipLoading] = useState(false);
  const [membershipError, setMembershipError] = useState(null);
  const [activeDistrictId, setActiveDistrictId] = useState(districtId);
  const [newDistrictKey, setNewDistrictKey] = useState("");
  const [membershipActionError, setMembershipActionError] = useState(null);
  const [addingMembership, setAddingMembership] = useState(false);
  const [activatingDistrictId, setActivatingDistrictId] = useState(null);
  const [downloadingInvoices, setDownloadingInvoices] = useState(false);
  const [invoiceDocuments, setInvoiceDocuments] = useState([]);
  const [invoiceDocumentsLoading, setInvoiceDocumentsLoading] = useState(false);
  const [invoiceDocumentsError, setInvoiceDocumentsError] = useState(null);
  const invoiceDocumentsCacheRef = useRef({});
  const [exportingInvoiceCsv, setExportingInvoiceCsv] = useState(false);

  const activeItem = menuItems.find((item) => item.key === activeKey) ?? menuItems[0];
  const selectedVendor = vendorProfiles.find((vendor) => vendor.id === selectedVendorId) ?? null;
  const selectedVendorName = selectedVendor?.name ?? "";
  const vendorMetrics = useMemo(() => computeVendorMetrics(vendorProfiles), [vendorProfiles]);

  useEffect(() => {
    setMemberships(initialMemberships ?? []);
  }, [initialMemberships]);

  useEffect(() => {
    setActiveDistrictId(districtId ?? null);
  }, [districtId]);

  // Keep the active tab in sync with the URL for deep links
  useEffect(() => {
    if (location.pathname === "/analytics") {
      setActiveKey("analytics");
    }
  }, [location.pathname]);

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
                const students = (invoice.students ?? []).map((student, studentIndex) => {
                  const trimmedName =
                    typeof student.name === "string" && student.name.trim().length
                      ? student.name.trim()
                      : "Unknown student";
                  const normalizedKey =
                    trimmedName !== "Unknown student"
                      ? trimmedName.toLowerCase()
                      : null;
                  const rawStudentId =
                    typeof student.student_id === "string" && student.student_id.trim().length
                      ? student.student_id.trim()
                      : typeof student.student_id === "number"
                      ? String(student.student_id)
                      : null;
                  const amountValue =
                    typeof student.amount === "number"
                      ? student.amount
                      : Number(student.amount) || 0;
                  const serviceLabel =
                    typeof student.service === "string" && student.service.trim().length
                      ? student.service.trim()
                      : null;

                  return {
                    id:
                      rawStudentId ??
                      (typeof student.id === "string"
                        ? student.id
                        : `student-${student.id ?? studentIndex}`),
                    originalLineItemId: student.id,
                    studentId: rawStudentId,
                    originalStudentId: rawStudentId,
                    name: trimmedName,
                    studentKey: normalizedKey,
                    service: serviceLabel,
                    amount: currencyFormatter.format(amountValue),
                    amountValue,
                    pdfUrl: student.pdf_url ?? null,
                    pdfS3Key: student.pdf_s3_key ?? null,
                    timesheetUrl: student.timesheet_url ?? null,
                  };
                });
              return {
                month: invoice.month,
                monthIndex,
                total: currencyFormatter.format(invoice.total ?? 0),
                totalValue: invoice.total ?? 0,
                status: invoice.status ? invoice.status.trim() : "",
                processedOn: invoice.processed_on ?? "Processing",
                pdfUrl: invoice.download_url ?? invoice.pdf_url ?? null,
                pdfS3Key: invoice.pdf_s3_key ?? null,
                timesheetCsvUrl: invoice.timesheet_csv_url ?? null,
                students: aggregateStudentEntries(students),
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

        const remitToAddress = formatPostalAddress(vendor.remit_to_address ?? null);

        const rawContactName = vendor.contact_name?.trim() ?? "";
        const contactName = isEmailLike(rawContactName) ? "" : rawContactName;

        const contactEmail = vendor.contact_email?.trim() ?? "";

        return {
          id: String(vendor.id),
          name: vendor.name,
          manager: contactName,
          email: isEmailLike(contactEmail) ? "" : contactEmail,
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

  const handleDistrictKeyChange = useCallback((event) => {
    const rawValue = event.target.value ?? "";
    const normalized = rawValue.replace(/[^a-zA-Z0-9-]/g, "").toUpperCase();
    setNewDistrictKey(normalized);
  }, []);

  const loadMemberships = useCallback(async () => {
    if (!isAuthenticated) {
      setMemberships([]);
      setActiveDistrictId(null);
      setMembershipError(null);
      return null;
    }

    setMembershipLoading(true);
    setMembershipError(null);
    try {
      const token = await getAccessTokenSilently();
      const collection = await fetchDistrictMemberships(token);
      setMemberships(collection.memberships ?? []);
      setActiveDistrictId(collection.active_district_id ?? null);
      return collection;
    } catch (error) {
      console.error("district_memberships_fetch_failed", error);
      setMemberships([]);
      setActiveDistrictId(null);
      setMembershipError(
        "We couldn't load your district access list. Try refreshing the page.",
      );
      return null;
    } finally {
      setMembershipLoading(false);
    }
  }, [getAccessTokenSilently, isAuthenticated]);

  const handleAddMembership = useCallback(
    async (event) => {
      event.preventDefault();
      if (addingMembership) {
        return;
      }

      const candidate = newDistrictKey.trim();
      if (!candidate) {
        setMembershipActionError("Enter a district access key to continue.");
        return;
      }

      setAddingMembership(true);
      setMembershipActionError(null);
      try {
        const token = await getAccessTokenSilently();
        const collection = await addDistrictMembership(token, candidate);
        setMemberships(collection.memberships ?? []);
        setActiveDistrictId(collection.active_district_id ?? null);
        setNewDistrictKey("");
        toast.success("District access key added.");
        if (typeof onMembershipChange === "function") {
          await onMembershipChange();
        }
      } catch (error) {
        console.error("district_membership_add_failed", error);
        setMembershipActionError(
          error instanceof Error && error.message
            ? error.message
            : "We couldn't add that access key. Please verify and try again.",
        );
      } finally {
        setAddingMembership(false);
      }
    },
    [addingMembership, getAccessTokenSilently, newDistrictKey, onMembershipChange],
  );

  const handleActivateMembership = useCallback(
    async (targetDistrictId) => {
      if (targetDistrictId == null || targetDistrictId === activeDistrictId) {
        return;
      }
      if (activatingDistrictId === targetDistrictId) {
        return;
      }

      setActivatingDistrictId(targetDistrictId);
      setMembershipActionError(null);
      try {
        const token = await getAccessTokenSilently();
        const collection = await activateDistrictMembership(
          token,
          targetDistrictId,
        );
        setMemberships(collection.memberships ?? []);
        setActiveDistrictId(collection.active_district_id ?? null);
        toast.success("Active district updated.");
        if (typeof onMembershipChange === "function") {
          await onMembershipChange();
        }
      } catch (error) {
        console.error("district_membership_activate_failed", error);
        setMembershipActionError(
          error instanceof Error && error.message
            ? error.message
            : "We couldn't switch districts. Please try again.",
        );
      } finally {
        setActivatingDistrictId(null);
      }
    },
    [activeDistrictId, activatingDistrictId, getAccessTokenSilently, onMembershipChange],
  );

  const loadVendors = useCallback(async () => {
    if (!isAuthenticated) {
      setVendorProfiles([]);
      setVendorsError(null);
      return;
    }

    if (activeDistrictId == null) {
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
  }, [
    activeDistrictId,
    getAccessTokenSilently,
    isAuthenticated,
    normalizeVendorOverview,
  ]);

  const loadDistrictProfile = useCallback(async () => {
    if (!isAuthenticated) {
      setDistrictProfile(null);
      setProfileError(null);
      return null;
    }

    if (activeDistrictId == null) {
      setDistrictProfile(null);
      setProfileError(
        "Add a district access key from Settings to connect to your workspace.",
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
  }, [activeDistrictId, getAccessTokenSilently, isAuthenticated]);

  const handleProfileSubmit = useCallback(
    async (values) => {
      setProfileSaving(true);
      setProfileFormError(null);
      try {
        const token = await getAccessTokenSilently();
        const profile = await updateDistrictProfile(token, values);
        setDistrictProfile(profile);
        setShowProfileForm(false);
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
  }, []);

  const initialProfileValues = useMemo(
    () => ({
      company_name: districtProfile?.company_name ?? "",
      contact_name: districtProfile?.contact_name ?? "",
      contact_email: districtProfile?.contact_email ?? "",
      phone_number: districtProfile?.phone_number ?? "",
      mailing_address: {
        street: districtProfile?.mailing_address?.street ?? "",
        city: districtProfile?.mailing_address?.city ?? "",
        state: districtProfile?.mailing_address?.state ?? "",
        postal_code: districtProfile?.mailing_address?.postal_code ?? "",
      },
    }),
    [
      districtProfile?.company_name,
      districtProfile?.contact_name,
      districtProfile?.contact_email,
      districtProfile?.phone_number,
      districtProfile?.mailing_address?.street,
      districtProfile?.mailing_address?.city,
      districtProfile?.mailing_address?.state,
      districtProfile?.mailing_address?.postal_code,
    ],
  );

  const formattedDistrictMailing = useMemo(
    () => formatPostalAddress(districtProfile?.mailing_address ?? null),
    [
      districtProfile?.mailing_address?.street,
      districtProfile?.mailing_address?.city,
      districtProfile?.mailing_address?.state,
      districtProfile?.mailing_address?.postal_code,
    ],
  );
  const computedActiveInvoiceDetails = useMemo(() => {
    if (!selectedVendor || !selectedInvoiceKey) {
      return null;
    }

    const invoiceRecord =
      selectedVendor.invoices[selectedInvoiceKey.year]?.find(
        (invoice) => invoice.month === selectedInvoiceKey.month,
      ) ?? null;

    if (!invoiceRecord) {
      return null;
    }

    const aggregatedStudents = aggregateStudentEntries(
      invoiceRecord.students ?? [],
    );

    return {
      ...invoiceRecord,
      year: selectedInvoiceKey.year,
      students: aggregatedStudents,
    };
  }, [selectedInvoiceKey, selectedVendor]);

  const selectedMonthNumber = useMemo(() => {
    if (!activeInvoiceDetails) {
      return null;
    }

    return resolveMonthNumber(
      activeInvoiceDetails.month,
      activeInvoiceDetails.monthIndex,
    );
  }, [activeInvoiceDetails]);

  useEffect(() => {
    if (!isAuthenticated) {
      setVendorProfiles([]);
      setVendorsError(null);
      setDistrictProfile(null);
      setProfileError(null);
      setShowProfileForm(false);
      setMemberships([]);
      setActiveDistrictId(null);
      setMembershipError(null);
      setNewDistrictKey("");
      return;
    }

    loadMemberships().catch(() => {});
  }, [isAuthenticated, loadMemberships]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (activeDistrictId == null) {
      setVendorProfiles([]);
      setVendorsError(null);
      setDistrictProfile(null);
      return;
    }

    loadVendors().catch(() => {});
    loadDistrictProfile().catch(() => {});
  }, [activeDistrictId, isAuthenticated, loadDistrictProfile, loadVendors]);

  useEffect(() => {
    setShowProfileForm(false);
  }, [districtProfile?.id]);

  useEffect(() => {
    if (
      selectedVendorId !== null &&
      !vendorProfiles.some((vendor) => vendor.id === selectedVendorId)
    ) {
      setSelectedVendorId(null);
    }
  }, [selectedVendorId, vendorProfiles]);

  useEffect(() => {
    if (activeKey !== "vendors") {
      setSelectedVendorId(null);
    }
  }, [activeKey]);

  useEffect(() => {
    setSelectedInvoiceKey(null);
  }, [activeKey, selectedVendorId]);

  useEffect(() => {
    if (!activeInvoiceDetails) {
      setInvoiceDocuments([]);
      setInvoiceDocumentsError(null);
      setInvoiceDocumentsLoading(false);
      setExportingInvoiceCsv(false);
    }
  }, [activeInvoiceDetails]);

  useEffect(() => {
    let ignore = false;

    if (!selectedVendorId || !activeInvoiceDetails) {
      return () => {
        ignore = true;
      };
    }

    const vendorNumericId = Number(selectedVendorId);
    if (!Number.isFinite(vendorNumericId) || vendorNumericId <= 0) {
      setInvoiceDocuments([]);
      setInvoiceDocumentsError(
        "We couldn't determine the vendor for these invoices.",
      );
      setInvoiceDocumentsLoading(false);
      return () => {
        ignore = true;
      };
    }

    if (!selectedMonthNumber || typeof activeInvoiceDetails.year !== "number") {
      setInvoiceDocuments([]);
      setInvoiceDocumentsError(
        "We couldn't determine which month to load invoices for.",
      );
      setInvoiceDocumentsLoading(false);
      return () => {
        ignore = true;
      };
    }

    const cacheKey = `${vendorNumericId}-${activeInvoiceDetails.year}-${String(
      selectedMonthNumber,
    ).padStart(2, "0")}`;
    const cached = invoiceDocumentsCacheRef.current[cacheKey];
    if (cached) {
      setInvoiceDocuments(cached.records ?? []);
      setInvoiceDocumentsError(null);
      setInvoiceDocumentsLoading(false);
      return () => {
        ignore = true;
      };
    }

    setInvoiceDocuments([]);
    setInvoiceDocumentsLoading(true);
    setInvoiceDocumentsError(null);

    (async () => {
      try {
        const accessToken = await getAccessTokenSilently();
        const response = await fetchVendorInvoicesForMonth(
          vendorNumericId,
          activeInvoiceDetails.year,
          selectedMonthNumber,
          accessToken,
        );

        if (ignore) {
          return;
        }

        const records = Array.isArray(response) ? response : [];
        const normalized = records
          .map((entry) => {
            const invoiceId = entry?.invoice_id ?? null;
            const amountValue =
              typeof entry?.amount === "number"
                ? entry.amount
                : parseCurrencyValue(entry?.amount ?? 0);
            const uploadedAt =
              typeof entry?.uploaded_at === "string"
                ? entry.uploaded_at.trim()
                : null;
            const uploadedAtTimestamp = uploadedAt
              ? Date.parse(uploadedAt)
              : Number.NaN;
            const statusValue =
              typeof entry?.status === "string"
                ? entry.status.trim()
                : "";

            const invoiceName =
              (typeof entry?.invoice_name === "string" &&
                entry.invoice_name.trim()) ||
              `Invoice ${invoiceId ?? ""}`.trim() ||
              "Invoice";
            return {
              invoiceId,
              vendorId: entry?.vendor_id ?? vendorNumericId,
              company:
                (typeof entry?.company === "string" && entry.company.trim()) ||
                selectedVendorName,
              invoiceName,
              invoiceNameDisplay: formatInvoiceDisplayName(invoiceName),
              s3Key:
                typeof entry?.s3_key === "string" && entry.s3_key.trim().length
                  ? entry.s3_key.trim()
                  : null,
              amountValue,
              amountDisplay: currencyFormatter.format(amountValue ?? 0),
              status: statusValue,
              uploadedAt,
              uploadedAtDisplay: formatDisplayDateTime(uploadedAt),
              uploadedAtTimestamp,
            };
          })
          .sort((a, b) => {
            const aTimestamp = Number.isFinite(a.uploadedAtTimestamp)
              ? a.uploadedAtTimestamp
              : -Infinity;
            const bTimestamp = Number.isFinite(b.uploadedAtTimestamp)
              ? b.uploadedAtTimestamp
              : -Infinity;

            if (aTimestamp !== bTimestamp) {
              return bTimestamp - aTimestamp;
            }

            return (b.invoiceId ?? 0) - (a.invoiceId ?? 0);
          });

        invoiceDocumentsCacheRef.current[cacheKey] = {
          records: normalized,
        };

        setInvoiceDocuments(normalized);
        setInvoiceDocumentsError(null);
      } catch (error) {
        if (ignore) {
          return;
        }

        console.error("district_vendor_invoices_fetch_failed", {
          error,
          vendorId: vendorNumericId,
          year: activeInvoiceDetails.year,
          month: selectedMonthNumber,
        });
        setInvoiceDocuments([]);
        setInvoiceDocumentsError(
          "We couldn't load the invoices for this month. Try again in a moment.",
        );
      } finally {
        if (!ignore) {
          setInvoiceDocumentsLoading(false);
        }
      }
    })();

    return () => {
      ignore = true;
    };
  }, [
    activeInvoiceDetails,
    getAccessTokenSilently,
    invoiceDocumentsCacheRef,
    selectedMonthNumber,
    selectedVendorId,
    selectedVendorName,
  ]);

  useEffect(() => {
    setActiveInvoiceDetails(computedActiveInvoiceDetails);
  }, [computedActiveInvoiceDetails]);

  const studentInvoiceCount = activeInvoiceDetails?.students?.length ?? 0;
  const invoiceDocumentCount = invoiceDocuments.length;
  const zipInvoiceCount = invoiceDocumentCount || studentInvoiceCount;

  const openInvoiceUrl = useCallback((url, errorMessage) => {
    if (!url) {
      if (errorMessage) {
        toast.error(errorMessage);
      }
      return;
    }

    try {
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (error) {
      console.error("Failed to open invoice link", error);
      toast.error("We couldn't open this invoice. Please try again.");
    }
  }, []);

  const requestInvoiceUrl = useCallback(
    async (s3Key, invoiceId) => {
      const accessToken = await getAccessTokenSilently();
      const response = await fetchInvoicePresignedUrl(s3Key, accessToken);
      const rawUrl = typeof response?.url === "string" ? response.url.trim() : "";

      if (!rawUrl) {
        throw new Error("Presigned URL missing from response");
      }

      if (invoiceId == null) {
        return rawUrl;
      }

      const cacheBuster = `_=${encodeURIComponent(String(invoiceId))}`;
      return `${rawUrl}${rawUrl.includes("?") ? "&" : "?"}${cacheBuster}`;
    },
    [getAccessTokenSilently],
  );

  const handleVendorInvoiceDownload = useCallback(async () => {
    const fallbackUrl = activeInvoiceDetails?.pdfUrl ?? null;
    const s3Key = activeInvoiceDetails?.pdfS3Key ?? null;
    const invoiceId = activeInvoiceDetails?.id ?? null;

    if (s3Key) {
      try {
        const presignedUrl = await requestInvoiceUrl(s3Key, invoiceId);
        openInvoiceUrl(presignedUrl, "Invoice file not available.");
        return;
      } catch (error) {
        console.error("Failed to fetch vendor invoice presigned URL", {
          error,
          invoiceId,
          s3Key,
        });
        toast.error("Unable to fetch this invoice. Please try again.");
      }
    }

    if (fallbackUrl) {
      openInvoiceUrl(fallbackUrl, "Invoice file not available.");
      return;
    }

    toast.error("Invoice file not available.");
  }, [
    activeInvoiceDetails?.id,
    activeInvoiceDetails?.pdfS3Key,
    activeInvoiceDetails?.pdfUrl,
    openInvoiceUrl,
    requestInvoiceUrl,
  ]);


  const handleDownloadAllInvoicesZip = useCallback(async () => {
    if (!activeInvoiceDetails) {
      toast.error("Select a month to download invoices.");
      return;
    }

    if (!zipInvoiceCount) {
      toast.error("No invoices are available for this month.");
      return;
    }

    const vendorId = selectedVendor?.id ?? null;
    if (vendorId == null) {
      toast.error("We couldn't determine the vendor for this download.");
      return;
    }

    const monthName = activeInvoiceDetails.month ?? "";
    const yearValue = activeInvoiceDetails.year ?? null;
    const monthIndex = MONTH_INDEX[monthName] ?? null;
    let normalizedMonth = null;

    if (monthIndex != null && typeof yearValue === "number") {
      normalizedMonth = `${yearValue}-${String(monthIndex + 1).padStart(2, "0")}`;
    } else {
      const sanitized = `${monthName}`.trim().replace(/\s+/g, "-");
      if (sanitized) {
        normalizedMonth = yearValue ? `${sanitized}-${yearValue}` : sanitized;
      }
    }

    if (!normalizedMonth) {
      toast.error("This month's invoices are missing schedule details.");
      return;
    }

    setDownloadingInvoices(true);

    try {
      const accessToken = await getAccessTokenSilently();
      const response = await fetchVendorInvoiceArchive(
        vendorId,
        normalizedMonth,
        accessToken,
      );

      const downloadUrl =
        typeof response?.download_url === "string"
          ? response.download_url.trim()
          : "";

      if (!downloadUrl) {
        throw new Error("Missing download URL in archive response");
      }

      openInvoiceUrl(
        downloadUrl,
        "We couldn't open the invoice archive. Please try again.",
      );
      toast.success("Your ZIP archive is ready with a CSV summary.");
    } catch (error) {
      console.error("Failed to prepare invoice archive", {
        error,
        vendorId,
        normalizedMonth,
      });
      toast.error("We couldn't prepare the invoice archive. Please try again.");
    } finally {
      setDownloadingInvoices(false);
    }
  }, [
    activeInvoiceDetails,
    getAccessTokenSilently,
    openInvoiceUrl,
    selectedVendor?.id,
    zipInvoiceCount,
  ]);

  const handleDownloadInvoiceDocument = useCallback(
    async (record) => {
      if (!record) {
        toast.error("We couldn't find that invoice.");
        return;
      }

      const s3Key = record.s3Key ?? null;
      const invoiceId = record.invoiceId ?? null;

      if (!s3Key) {
        toast.error("This invoice does not have a file to download yet.");
        return;
      }

      try {
        const presignedUrl = await requestInvoiceUrl(s3Key, invoiceId);
        openInvoiceUrl(
          presignedUrl,
          "We couldn't open this invoice. Please try again.",
        );
      } catch (error) {
        console.error("district_invoice_document_download_failed", {
          error,
          invoiceId,
          s3Key,
        });
        toast.error("We couldn't download this invoice. Please try again.");
      }
    },
    [openInvoiceUrl, requestInvoiceUrl],
  );

  const handleExportInvoicesCsv = useCallback(() => {
    if (!invoiceDocuments.length) {
      toast.error("No invoices are available to export for this month.");
      return;
    }

    if (!activeInvoiceDetails || !selectedMonthNumber) {
      toast.error("We couldn't determine the selected month for export.");
      return;
    }

    setExportingInvoiceCsv(true);

    try {
      const header = ["Vendor", "Invoice Name", "Amount", "Uploaded At"];
      const rows = invoiceDocuments.map((record) => [
        record.company ?? selectedVendorName,
        record.invoiceName ?? "",
        Number.isFinite(record.amountValue)
          ? Number(record.amountValue).toFixed(2)
          : "",
        record.uploadedAt ?? "",
      ]);

      const csvContent = [header, ...rows]
        .map((row) =>
          row
            .map((value) => {
              const text =
                value === null || value === undefined ? "" : String(value);
              if (/[",\n]/.test(text)) {
                return `"${text.replace(/"/g, '""')}"`;
              }
              return text;
            })
            .join(","),
        )
        .join("\r\n");

      const blob = new Blob([csvContent], {
        type: "text/csv;charset=utf-8;",
      });
      const vendorSegment = sanitizeFilenameSegment(
        selectedVendorName || `vendor-${selectedVendorId ?? ""}`,
      );
      const filename = `invoices-${vendorSegment}-${activeInvoiceDetails.year}-${String(
        selectedMonthNumber,
      ).padStart(2, "0")}.csv`;

      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();

      setTimeout(() => {
        URL.revokeObjectURL(link.href);
        document.body.removeChild(link);
      }, 0);

      toast.success("Invoice CSV exported.");
    } catch (error) {
      console.error("district_invoice_csv_export_failed", {
        error,
        vendorId: selectedVendorId,
        year: activeInvoiceDetails?.year,
        month: selectedMonthNumber,
      });
      toast.error("We couldn't export the invoices. Please try again.");
    } finally {
      setExportingInvoiceCsv(false);
    }
  }, [
    activeInvoiceDetails,
    invoiceDocuments,
    selectedMonthNumber,
    selectedVendorId,
    selectedVendorName,
  ]);
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

    const contactDetails = [selectedVendor.phone]
      .map((value) => (value && !isEmailLike(value) ? value : ""))
      .filter(Boolean);
    if (contactDetails.length) {
      segments.push(contactDetails.join(" • "));
    }

    return segments.length ? segments.join(" • ") : null;
  }, [selectedVendor]);

  const vendorHeaderContactLine = useMemo(() => {
    if (!selectedVendor) {
      return null;
    }

    const segments = [selectedVendor.manager, selectedVendor.phone]
      .map((value) => (value ? value.trim() : ""))
      .map((value) => (value && !isEmailLike(value) ? value : ""))
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
            </div>
            <nav className="space-y-1 px-2 pb-4">
              {menuItems.map((item) => {
                const isActive = activeKey === item.key;
                const className = `group flex w-full items-center rounded-xl px-4 py-3 text-left text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70 ${
                  isActive
                    ? "bg-slate-100 text-slate-900"
                    : "text-slate-200 hover:bg-white/10 hover:text-white"
                }`;

                if (item.key === "analytics") {
                  return (
                    <Link
                      key={item.key}
                      to={item.route ?? "/analytics"}
                      onClick={() => setActiveKey("analytics")}
                      className={className}
                    >
                      <span>{item.label}</span>
                    </Link>
                  );
                }

                const handleClick = () => {
                  if (item.route) navigate(item.route);
                  setActiveKey(item.key);
                };

                return (
                  <button key={item.key} onClick={handleClick} className={className} type="button">
                    <span>{item.label}</span>
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
              {activeItem.key === "vendors" ? "Vendor Partner Overview" : activeItem.label}
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
                        className="flex h-full flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:border-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
                        type="button"
                      >
                        <p className="text-sm font-semibold text-slate-900">{vendor.name}</p>
                        <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
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
                      <button
                        type="button"
                        onClick={handleVendorInvoiceDownload}
                        className="inline-flex items-center rounded-full bg-amber-500 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                      >
                        Download PDF Invoice
                      </button>
                    ) : (
                      <span className="text-xs text-slate-500">
                        Invoice file not available
                      </span>
                    )}
                  </div>
                </div>

                {vendorOverviewHighlights.length && !activeInvoiceDetails ? (
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

                {activeInvoiceDetails ? (
                  <div className="space-y-6">
                    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                        Student invoices
                      </p>
                      <h5 className="mt-2 text-lg font-semibold text-slate-900">
                        Download all invoices for {activeInvoiceDetails.month} {activeInvoiceDetails.year}
                      </h5>
                      <p className="mt-1 text-sm text-slate-600">
                        Get a zipped archive containing every student invoice for this month along with a CSV summary for quick review.
                      </p>
                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={handleDownloadAllInvoicesZip}
                          disabled={downloadingInvoices || !zipInvoiceCount}
                          className={`inline-flex items-center rounded-full px-4 py-2 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 ${
                            downloadingInvoices || !zipInvoiceCount
                              ? "cursor-not-allowed bg-amber-200 text-amber-800"
                              : "bg-amber-500 text-white hover:bg-amber-600"
                          }`}
                        >
                          {downloadingInvoices
                            ? "Preparing download…"
                            : "Download ZIP + CSV"}
                        </button>
                        <span className="text-xs text-slate-500">
                          {zipInvoiceCount
                            ? `${zipInvoiceCount} invoice${zipInvoiceCount === 1 ? "" : "s"} included`
                            : "No invoices available"}
                        </span>
                      </div>
                      {zipInvoiceCount ? (
                        <p className="mt-2 text-xs text-slate-500">
                          The archive opens in a new tab and includes every PDF plus a CSV summary of filenames, S3 keys, dates, and sizes.
                        </p>
                      ) : (
                        <p className="mt-2 text-xs text-slate-500">
                          When invoices are uploaded, you'll be able to download them here as a single archive.
                        </p>
                      )}
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                          Monthly invoice files
                        </p>
                        <h5 className="mt-2 text-lg font-semibold text-slate-900">
                          Invoices uploaded for {activeInvoiceDetails.month} {activeInvoiceDetails.year}
                        </h5>
                        <p className="mt-1 text-sm text-slate-600">
                          Review the invoices submitted by {selectedVendorName || "this vendor"} and download individual files as needed.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={handleExportInvoicesCsv}
                        disabled={exportingInvoiceCsv || !invoiceDocuments.length}
                        className={`inline-flex items-center rounded-full px-4 py-2 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 ${
                          exportingInvoiceCsv || !invoiceDocuments.length
                            ? "cursor-not-allowed bg-slate-200 text-slate-500"
                            : "bg-amber-500 text-white hover:bg-amber-600"
                        }`}
                      >
                        {exportingInvoiceCsv ? "Exporting…" : "Export CSV"}
                      </button>
                    </div>
                    {invoiceDocumentsError ? (
                      <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                        {invoiceDocumentsError}
                      </div>
                    ) : null}
                    {invoiceDocumentsLoading ? (
                      <p className="mt-4 text-sm text-slate-600">Loading invoices…</p>
                    ) : null}
                    {!invoiceDocumentsLoading && !invoiceDocumentsError && !invoiceDocuments.length ? (
                      <p className="mt-4 text-sm text-slate-500">
                        No invoices were uploaded for this month yet.
                      </p>
                    ) : null}
                    {invoiceDocuments.length ? (
                      <div className="mt-4 overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm">
                          <thead>
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-widest text-slate-500 first:pl-0 last:pr-0">
                                Invoice
                              </th>
                              <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-widest text-slate-500 first:pl-0 last:pr-0">
                                Amount
                              </th>
                              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-widest text-slate-500 first:pl-0 last:pr-0">
                                Uploaded
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200">
                            {invoiceDocuments.map((document, index) => (
                              <tr
                                key={`${document.invoiceId ?? document.invoiceName ?? "invoice"}-${document.s3Key ?? index}`}
                              >
                                <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900 first:pl-0 last:pr-0">
                                  {document.invoiceNameDisplay ?? document.invoiceName}
                                </td>
                                <td className="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900 first:pl-0 last:pr-0">
                                  {document.amountDisplay}
                                </td>
                                <td className="whitespace-nowrap px-4 py-3 text-slate-600 first:pl-0 last:pr-0">
                                  {document.uploadedAtDisplay ?? "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-amber-500">{selectedVendor.name}</p>
                    <h4 className="mt-1 text-2xl font-semibold text-slate-900">Select a month</h4>
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

        ) : activeItem.key === "analytics" ? (
          <div className="mt-8">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-widest text-amber-500">Analytics</p>
              <h4 className="mt-1 text-2xl font-semibold text-slate-900">AI Analytics Assistant</h4>
              <p className="mt-2 text-sm text-slate-600">
                Ask natural-language questions about invoices, vendors, students, monthly totals, or spending summaries.
              </p>
              <div className="mt-4">
                <ChatAgent districtKey={districtProfile?.district_key} />
              </div>
            </div>
          </div>
        ) : activeItem.key === "settings" ? (
            <div className="mt-8 space-y-6">
              <div className="space-y-6">
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
                          {formattedDistrictMailing ? (
                            <p className="whitespace-pre-line">
                              {formattedDistrictMailing}
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

                {!profileLoading && !profileError && !districtProfile ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                    No district profile data is available for this workspace yet.
                  </div>
                ) : null}
              </div>

              <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                <h4 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
                  District access keys
                </h4>
                <p className="mt-2 text-sm text-slate-600">
                  Enter the secure access keys that administrators share with your team to unlock district consoles.
                </p>
                <form
                  onSubmit={handleAddMembership}
                  className="mt-4 flex flex-col gap-3 sm:flex-row"
                >
                  <div className="flex flex-1 items-center gap-3 rounded-xl border border-slate-300 bg-white px-4 py-3 transition focus-within:border-amber-400 focus-within:ring-2 focus-within:ring-amber-200">
                    <input
                      type="text"
                      className="w-full border-none bg-transparent text-sm font-medium uppercase tracking-widest text-slate-900 focus:outline-none"
                      placeholder="e.g., ASCS-1234-5678"
                      value={newDistrictKey}
                      onChange={handleDistrictKeyChange}
                      disabled={addingMembership}
                    />
                  </div>
                  <button
                    type="submit"
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-3 text-sm font-semibold text-white shadow transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={addingMembership}
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    {addingMembership ? "Adding…" : "Add key"}
                  </button>
                </form>
                {membershipActionError ? (
                  <p className="mt-3 text-sm font-medium text-red-600">
                    {membershipActionError}
                  </p>
                ) : null}
                <p className="mt-3 text-xs text-slate-500">
                  Keys are not case sensitive—we’ll normalize them for you automatically.
                </p>
              </section>

              <section className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
                    Linked districts
                  </h4>
                  {membershipLoading ? (
                    <span className="text-xs text-slate-500">Updating…</span>
                  ) : null}
                </div>
                {membershipError ? (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                    {membershipError}
                  </div>
                ) : memberships.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-5 text-sm text-slate-600">
                    Add a district key to unlock your console access.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {memberships.map((membership) => (
                      <div
                        key={membership.district_id}
                        className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-300 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <p className="text-base font-semibold text-slate-900">
                            {membership.company_name}
                          </p>
                          <p className="mt-1 font-mono text-xs tracking-widest text-amber-700">
                            {membership.district_key}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {membership.is_active ? (
                            <span className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                              Active
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleActivateMembership(membership.district_id)}
                              disabled={
                                activatingDistrictId === membership.district_id ||
                                addingMembership
                              }
                              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {activatingDistrictId === membership.district_id
                                ? "Switching…"
                                : "Make active"}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
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
