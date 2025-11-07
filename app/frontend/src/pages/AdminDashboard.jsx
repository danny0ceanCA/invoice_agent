import { Link } from "react-router-dom";
import { Users2 } from "lucide-react";

export default function AdminDashboard({ currentUser }) {
  const cards = [
    {
      title: "Vendor Workspace Overview",
      description: "Track vendor enrollments, onboarding progress, and active contracts.",
    },
    {
      title: "District Insights",
      description: "Upcoming releases will surface analytics for approvals, payments, and staffing.",
    },
  ];

  return (
    <div className="space-y-6 text-slate-700">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Admin Console</h2>
        <p className="mt-1 text-sm text-slate-600">
          Manage user access, monitor district and vendor workspaces, and keep your operations running smoothly.
        </p>
      </div>

      {currentUser?.role === "admin" && (
        <div className="grid gap-4 md:grid-cols-3">
          <Link
            to="/admin/users"
            className="group flex h-full flex-col justify-between rounded-xl border border-indigo-100 bg-gradient-to-r from-indigo-50 via-sky-50 to-cyan-50 p-6 text-indigo-900 shadow-sm transition-transform duration-200 ease-out hover:-translate-y-1 hover:shadow-xl"
            aria-label="Open user management dashboard"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-wide text-indigo-600">Administration</p>
                <h3 className="mt-2 text-xl font-semibold text-indigo-950">User Management</h3>
              </div>
              <div className="rounded-full bg-indigo-100 p-2 text-indigo-600">
                <Users2 className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-indigo-700">
              Approve pending accounts, adjust roles, and deactivate access — all in one place.
            </p>
            <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-indigo-600">
              Manage users
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </span>
          </Link>

          {cards.map((card) => (
            <div
              key={card.title}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
            >
              <p className="text-sm font-semibold text-slate-900">{card.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{card.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

