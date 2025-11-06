import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

import { RoleSelectionForm } from "../components/RoleSelectionForm";
import VendorDashboard from "./VendorDashboard.jsx";
import DistrictDashboard from "./DistrictDashboard.jsx";
import {
  fetchCurrentUser,
  type CurrentUserResponse,
} from "../api/auth";

function AdminConsole() {
  return (
    <div className="space-y-4 text-slate-700">
      <p className="text-base font-semibold">Admin Console</p>
      <p className="text-sm">
        Administrative tooling for dataset profiles will land shortly. In the meantime you can review vendor and district
        dashboards directly.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Vendor Workspace Overview</p>
          <p className="mt-1 text-xs text-slate-600">Track vendor enrollments, onboarding progress, and active contracts.</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">District Insights</p>
          <p className="mt-1 text-xs text-slate-600">Upcoming releases will surface analytics for approvals, payments, and staffing.</p>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const { isAuthenticated, isLoading, loginWithRedirect, logout, user, getAccessTokenSilently } = useAuth0();
  const [profile, setProfile] = useState<CurrentUserResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      const token = await getAccessTokenSilently();
      const data = await fetchCurrentUser(token);
      setProfile(data);
      return data;
    } catch (error) {
      console.error("profile_fetch_failed", error);
      setProfile(null);
      setProfileError("We couldn't load your workspace details. Please refresh the page or try again later.");
      throw error;
    } finally {
      setProfileLoading(false);
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    if (!isAuthenticated) {
      setProfile(null);
      setProfileError(null);
      return;
    }

    loadProfile().catch(() => {
      /* error already captured in state */
    });
  }, [isAuthenticated, loadProfile]);

  const displayName = profile?.name ?? user?.name ?? user?.email ?? "Account";

  const dashboardContent = useMemo(() => {
    if (!profile?.role) {
      return null;
    }

    if (profile.role === "vendor") {
      return <VendorDashboard vendorId={profile.vendor_id ?? null} />;
    }

    if (profile.role === "district") {
      return <DistrictDashboard />;
    }

    if (profile.role === "admin") {
      return <AdminConsole />;
    }

    return null;
  }, [profile]);

  let mainContent: JSX.Element;
  if (isLoading) {
    mainContent = <div className="text-sm text-slate-600">Checking session…</div>;
  } else if (!isAuthenticated) {
    mainContent = (
      <div className="space-y-3 text-sm text-slate-600">
        <p>Please log in to access the invoice automation portal.</p>
        <button
          type="button"
          className="rounded bg-amber-500 px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600"
          onClick={() => loginWithRedirect()}
        >
          Log in
        </button>
      </div>
    );
  } else if (profileLoading && !profile) {
    mainContent = <div className="text-sm text-slate-600">Loading your workspace…</div>;
  } else if (profileError) {
    mainContent = <div className="text-sm text-red-600">{profileError}</div>;
  } else if (profile?.needs_role_selection) {
    mainContent = (
      <RoleSelectionForm
        onRoleSelected={async () => {
          await loadProfile();
        }}
      />
    );
  } else if (!profile) {
    mainContent = <div className="text-sm text-slate-600">We couldn't load your profile.</div>;
  } else if (profileLoading) {
    mainContent = <div className="text-sm text-slate-600">Loading dashboard…</div>;
  } else if (!dashboardContent) {
    mainContent = <div className="text-sm text-slate-600">Your account is active, but no dashboards are currently available for your role.</div>;
  } else {
    mainContent = dashboardContent;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-6 px-6 py-4">
          <h1 className="text-xl font-semibold">ASCS Invoice Automation</h1>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              {isAuthenticated ? (
                <>
                  <span className="text-sm text-slate-600">Signed in as {displayName}</span>
                  <button
                    type="button"
                    className="rounded border border-slate-200 px-3 py-1 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
                    onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                  >
                    Log out
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="rounded bg-amber-500 px-3 py-1 text-sm font-semibold text-white shadow transition hover:bg-amber-600"
                  onClick={() => loginWithRedirect()}
                >
                  Log in
                </button>
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="rounded-lg border bg-white p-6 shadow-sm">{mainContent}</div>
      </main>
    </div>
  );
}
