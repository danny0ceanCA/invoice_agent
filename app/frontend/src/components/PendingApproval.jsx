import { Info } from "lucide-react";

export default function PendingApproval() {
  return (
    <div className="pending-approval rounded-lg border border-slate-200 bg-slate-50 p-6 text-slate-700">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-200 text-slate-600">
          <Info aria-hidden="true" className="h-5 w-5" />
        </span>
        <h2 className="text-xl font-semibold text-slate-900">
          Your account has been created
        </h2>
      </div>
      <p className="text-sm text-slate-600">
        Your account is awaiting admin approval. You’ll receive access once
        approved.
      </p>
    </div>
  );
}
