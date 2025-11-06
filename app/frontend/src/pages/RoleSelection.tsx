import type { RoleSelectionOption } from "../api/auth";

interface RoleSelectionProps {
  onSelect(role: RoleSelectionOption): Promise<void> | void;
  isSubmitting: boolean;
  error?: string | null;
}

const roles: { key: RoleSelectionOption; title: string; description: string }[] = [
  {
    key: "vendor",
    title: "Vendor",
    description: "Submit invoices, upload timesheets, and monitor processing jobs.",
  },
  {
    key: "district",
    title: "District Staff",
    description: "Review vendor submissions, manage approvals, and access analytics dashboards.",
  },
];

export function RoleSelection({ onSelect, isSubmitting, error }: RoleSelectionProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-slate-900">Welcome! Choose your workspace</h2>
        <p className="text-sm text-slate-600">
          Tell us how you collaborate with the district so we can tailor the portal to your workflows.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {roles.map((role) => (
          <button
            key={role.key}
            type="button"
            onClick={() => onSelect(role.key)}
            disabled={isSubmitting}
            className="rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-amber-400 hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 disabled:opacity-60"
          >
            <div className="text-base font-semibold text-slate-900">{role.title}</div>
            <p className="mt-1 text-sm text-slate-600">{role.description}</p>
          </button>
        ))}
      </div>
      {error ? <div className="text-sm font-medium text-red-600">{error}</div> : null}
      <p className="text-xs text-slate-500">
        You can request access changes from an administrator after completing onboarding.
      </p>
    </div>
  );
}
