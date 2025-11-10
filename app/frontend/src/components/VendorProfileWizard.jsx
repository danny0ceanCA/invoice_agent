import { useEffect, useMemo, useState } from "react";

const PHONE_DIGIT_LENGTH = 10;
const PHONE_INPUT_PATTERN = /^\(\d{3}\)-\d{3}-\d{4}$/;
const STATE_PATTERN = /^[A-Za-z]{2}$/;
const POSTAL_CODE_PATTERN = /^\d{5}(?:-\d{4})?$/;

const PROFILE_STEPS = [
  {
    id: "company",
    field: "company_name",
    title: "Company name",
    description: "We use this on invoices and communications.",
    placeholder: "Acme Tutoring Co.",
  },
  {
    id: "contactName",
    field: "contact_name",
    title: "Primary contact name",
    description: "Who's the best person for us to reach out to?",
    placeholder: "Jordan Smith",
  },
  {
    id: "contactEmail",
    field: "contact_email",
    title: "Contact email",
    description: "We'll send confirmations and updates here.",
    placeholder: "jordan@example.com",
  },
  {
    id: "phone",
    field: "phone_number",
    title: "Phone number",
    description: "Include a 10-digit number we can call with questions.",
    placeholder: "(555)-123-4567",
  },
  {
    id: "remitAddress",
    field: "remit_to_address",
    title: "Remit-to address",
    description:
      "Where should districts send payment? Enter the street, city, state, and ZIP.",
  },
];

function stripPhoneNumber(value = "") {
  return value.replace(/\D/g, "").slice(0, PHONE_DIGIT_LENGTH);
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

function normalizePostalAddress(address = {}) {
  return {
    street: (address.street ?? "").trim(),
    city: (address.city ?? "").trim(),
    state: (address.state ?? "").trim().toUpperCase(),
    postal_code: (address.postal_code ?? "").trim(),
  };
}

function normalizeProfileValues(values) {
  const phoneDigits = stripPhoneNumber(values.phone_number);

  return {
    company_name: values.company_name.trim(),
    contact_name: values.contact_name.trim(),
    contact_email: values.contact_email.trim().toLowerCase(),
    phone_number: phoneDigits,
    remit_to_address: normalizePostalAddress(values.remit_to_address),
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

  const address = values.remit_to_address ?? {};
  if (!address.street || address.street.length < 3) {
    return "Enter a valid street address.";
  }

  if (!address.city || address.city.length < 2) {
    return "Enter a valid city.";
  }

  if (!address.state || !STATE_PATTERN.test(address.state)) {
    return "Enter a two-letter state abbreviation.";
  }

  if (!address.postal_code || !POSTAL_CODE_PATTERN.test(address.postal_code)) {
    return "Enter a valid ZIP code (##### or #####-####).";
  }

  return null;
}

function validateStep(stepId, values) {
  const normalized = normalizeProfileValues(values);

  switch (stepId) {
    case "company":
      if (normalized.company_name.length === 0) {
        return "Company name is required.";
      }
      return null;
    case "contactName":
      if (normalized.contact_name.length === 0) {
        return "Primary contact name is required.";
      }
      return null;
    case "contactEmail":
      if (normalized.contact_email.length === 0) {
        return "Contact email is required.";
      }
      return null;
    case "phone":
      if (normalized.phone_number.length === 0) {
        return "Phone number is required.";
      }
      return null;
    case "remitAddress":
      if (!normalized.remit_to_address.street) {
        return "Street address is required.";
      }
      if (!normalized.remit_to_address.city) {
        return "City is required.";
      }
      if (!normalized.remit_to_address.state) {
        return "State is required.";
      }
      if (!normalized.remit_to_address.postal_code) {
        return "ZIP code is required.";
      }
      return null;
    default:
      return null;
  }
}

export default function VendorProfileWizard({ initialValues, onSubmit, onClose }) {
  const memoizedInitialValues = useMemo(
    () => ({
      company_name: initialValues?.company_name ?? "",
      contact_name: initialValues?.contact_name ?? "",
      contact_email: initialValues?.contact_email ?? "",
      phone_number: formatPhoneNumberForInput(initialValues?.phone_number ?? ""),
      remit_to_address: {
        street: initialValues?.remit_to_address?.street ?? "",
        city: initialValues?.remit_to_address?.city ?? "",
        state: initialValues?.remit_to_address?.state ?? "",
        postal_code: initialValues?.remit_to_address?.postal_code ?? "",
      },
    }),
    [
      initialValues?.company_name,
      initialValues?.contact_name,
      initialValues?.contact_email,
      initialValues?.phone_number,
      initialValues?.remit_to_address?.street,
      initialValues?.remit_to_address?.city,
      initialValues?.remit_to_address?.state,
      initialValues?.remit_to_address?.postal_code,
    ],
  );

  const [currentStep, setCurrentStep] = useState(0);
  const [formValues, setFormValues] = useState(() => memoizedInitialValues);
  const [validationError, setValidationError] = useState(null);
  const [submitError, setSubmitError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setFormValues(memoizedInitialValues);
    setCurrentStep(0);
    setValidationError(null);
    setSubmitError(null);
  }, [memoizedInitialValues]);

  const currentStepConfig = useMemo(
    () => PROFILE_STEPS[currentStep] ?? PROFILE_STEPS[0],
    [currentStep],
  );

  function handleChange(event) {
    const { name, value } = event.target;
    if (name === "phone_number") {
      setFormValues((previous) => ({
        ...previous,
        [name]: formatPhoneNumberForInput(value),
      }));
      return;
    }

    if (name.startsWith("remit_to_address.")) {
      const [, field] = name.split(".");
      setFormValues((previous) => ({
        ...previous,
        remit_to_address: {
          ...previous.remit_to_address,
          [field]: value,
        },
      }));
      return;
    }

    setFormValues((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  async function handleNext(event) {
    event.preventDefault();

    const step = PROFILE_STEPS[currentStep];
    if (!step) return;

    const stepValidation = validateStep(step.id, formValues);
    if (stepValidation) {
      setValidationError(stepValidation);
      return;
    }

    setValidationError(null);
    setSubmitError(null);

    if (currentStep === PROFILE_STEPS.length - 1) {
      await handleSubmit();
      return;
    }

    setCurrentStep((previous) => Math.min(previous + 1, PROFILE_STEPS.length - 1));
  }

  async function handleSubmit() {
    if (isSubmitting) {
      return;
    }

    const normalizedValues = normalizeProfileValues(formValues);
    const validationMessage = validateProfileValues(normalizedValues);

    if (validationMessage) {
      setValidationError(validationMessage);
      return;
    }

    setValidationError(null);
    setSubmitError(null);
    setIsSubmitting(true);

    try {
      await onSubmit?.(normalizedValues);
      onClose?.();
    } catch (err) {
      const message = err?.message ?? "We couldn't save your profile. Please try again.";
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60">
      <div className="flex h-full w-full items-center justify-center px-4 py-10">
        <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-xl">
          <header className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-500">
              Vendor Profile Setup
            </p>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">
                  Tell us about your company
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  Complete these quick steps to unlock your vendor workspace.
                </p>
              </div>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Step {currentStep + 1} of {PROFILE_STEPS.length}
              </span>
            </div>
          </header>

          <form className="mt-8 space-y-6" onSubmit={handleNext}>
            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900">
                {currentStepConfig.title}
              </h3>
              <p className="text-sm text-slate-600">{currentStepConfig.description}</p>
            </div>

            {currentStepConfig.field === "company_name" ? (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700" htmlFor="company_name">
                  Company name
                </label>
                <input
                  id="company_name"
                  type="text"
                  name="company_name"
                  value={formValues.company_name}
                  onChange={handleChange}
                  autoFocus
                  placeholder={currentStepConfig.placeholder}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
            ) : null}

            {currentStepConfig.field === "contact_name" ? (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700" htmlFor="contact_name">
                  Primary contact name
                </label>
                <input
                  id="contact_name"
                  type="text"
                  name="contact_name"
                  value={formValues.contact_name}
                  onChange={handleChange}
                  autoFocus
                  placeholder={currentStepConfig.placeholder}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
            ) : null}

            {currentStepConfig.field === "contact_email" ? (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700" htmlFor="contact_email">
                  Contact email
                </label>
                <input
                  id="contact_email"
                  type="email"
                  name="contact_email"
                  value={formValues.contact_email}
                  onChange={handleChange}
                  autoFocus
                  placeholder={currentStepConfig.placeholder}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
            ) : null}

            {currentStepConfig.field === "phone_number" ? (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700" htmlFor="phone_number">
                  Phone number
                </label>
                <input
                  id="phone_number"
                  type="tel"
                  name="phone_number"
                  value={formValues.phone_number}
                  onChange={handleChange}
                  inputMode="tel"
                  pattern={PHONE_INPUT_PATTERN.source}
                  placeholder={currentStepConfig.placeholder}
                  autoFocus
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
                <p className="text-xs text-slate-500">Format: (###)-###-####</p>
              </div>
            ) : null}

            {currentStepConfig.field === "remit_to_address" ? (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label
                    className="block text-sm font-medium text-slate-700"
                    htmlFor="remit_to_address.street"
                  >
                    Street address
                  </label>
                  <input
                    id="remit_to_address.street"
                    type="text"
                    name="remit_to_address.street"
                    value={formValues.remit_to_address.street}
                    onChange={handleChange}
                    autoFocus
                    placeholder="Responsive Healthcare Associates"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2 sm:col-span-2">
                    <label
                      className="block text-sm font-medium text-slate-700"
                      htmlFor="remit_to_address.city"
                    >
                      City
                    </label>
                    <input
                      id="remit_to_address.city"
                      type="text"
                      name="remit_to_address.city"
                      value={formValues.remit_to_address.city}
                      onChange={handleChange}
                      placeholder="Sacramento"
                      className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      className="block text-sm font-medium text-slate-700"
                      htmlFor="remit_to_address.state"
                    >
                      State
                    </label>
                    <input
                      id="remit_to_address.state"
                      type="text"
                      name="remit_to_address.state"
                      value={formValues.remit_to_address.state}
                      onChange={handleChange}
                      placeholder="CA"
                      maxLength={2}
                      className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm uppercase text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      className="block text-sm font-medium text-slate-700"
                      htmlFor="remit_to_address.postal_code"
                    >
                      ZIP code
                    </label>
                    <input
                      id="remit_to_address.postal_code"
                      type="text"
                      name="remit_to_address.postal_code"
                      value={formValues.remit_to_address.postal_code}
                      onChange={handleChange}
                      placeholder="95824"
                      className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                    />
                  </div>
                </div>
              </div>
            ) : null}

            {validationError ? (
              <p className="text-sm text-red-600">{validationError}</p>
            ) : null}
            {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() =>
                  setCurrentStep((previous) => Math.max(previous - 1, 0))
                }
                disabled={currentStep === 0 || isSubmitting}
                className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Back
              </button>

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex items-center justify-center rounded-full bg-amber-500 px-5 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting
                  ? "Submitting…"
                  : currentStep === PROFILE_STEPS.length - 1
                    ? "Submit"
                    : "Next"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
