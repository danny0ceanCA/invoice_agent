import { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

import { API_BASE } from "../api/auth";

type RoleOption = "vendor" | "district";

type RoleSelectionFormProps = {
  onRoleSelected: () => Promise<void> | void;
};

export function RoleSelectionForm({ onRoleSelected }: RoleSelectionFormProps) {
  const { getAccessTokenSilently } = useAuth0();
  const [isSubmitting, setIsSubmitting] = useState<RoleOption | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = async (role: RoleOption) => {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(role);
    setError(null);
    setMessage("Saving choice…");

    try {
      const token = await getAccessTokenSilently();
      const response = await fetch(`${API_BASE}/auth/set-role`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ role }),
      });

      if (!response.ok) {
        const details = await response.text();
        throw new Error(details || `Unable to save role (status ${response.status})`);
      }

      setMessage("Loading dashboard…");
      await onRoleSelected();
    } catch (submitError) {
      console.error("role_selection_error", submitError);
      setError("We couldn’t save your choice. Please try again.");
      setMessage(null);
    } finally {
      setIsSubmitting(null);
    }
  };

  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center gap-6 text-center">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-slate-900">Welcome! Choose your workspace</h2>
        <p className="text-sm text-slate-600">Tell us how you collaborate with the district so we can tailor your experience.</p>
      </div>
      <div className="flex flex-col gap-4 md:flex-row">
        <button
          type="button"
          className="w-56 rounded-lg border border-slate-200 bg-white px-6 py-4 text-lg font-semibold text-slate-900 shadow-sm transition hover:border-amber-400 hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => handleSelect("vendor")}
          disabled={Boolean(isSubmitting)}
        >
          I’m a Vendor
        </button>
        <button
          type="button"
          className="w-56 rounded-lg border border-slate-200 bg-white px-6 py-4 text-lg font-semibold text-slate-900 shadow-sm transition hover:border-amber-400 hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => handleSelect("district")}
          disabled={Boolean(isSubmitting)}
        >
          I’m District Staff
        </button>
      </div>
      {message ? <div className="text-sm text-slate-600">{message}</div> : null}
      {error ? <div className="text-sm font-medium text-red-600">{error}</div> : null}
      <p className="text-xs text-slate-500">You can request access changes from an administrator after onboarding.</p>
    </div>
  );
}
