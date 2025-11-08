import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import { RoleSelectionForm } from "../components/RoleSelectionForm";
import PendingApproval from "../components/PendingApproval.jsx";
import VendorDashboard from "./VendorDashboard.jsx";
import DistrictDashboard from "./DistrictDashboard.jsx";
import AdminDashboard from "./AdminDashboard.jsx";
import AdminUserDashboard from "./AdminUserDashboard.jsx";
import {
  fetchCurrentUser,
  type ApiError,
  type CurrentUserResponse,
} from "../api/auth";

const isApiError = (value: unknown): value is ApiError =>
  typeof value === "object" && value !== null && "status" in value;

export function App() {
  const { isAuthenticated, isLoading, loginWithRedirect, logout, user, getAccessTokenSilently } = useAuth0();
  const [profile, setProfile] = useState<CurrentUserResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState(false);

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);
    setPendingApproval(false);
    try {
      const token = await getAccessTokenSilently();
      const data = await fetchCurrentUser(token);
      setProfile(data);
      return data;
    } catch (error: unknown) {
      console.error("profile_fetch_failed", error);
      setProfile(null);
      if (isApiError(error) && error.status === 403) {
        setPendingApproval(true);
        setProfileError(null);
        return null;
      }
      setProfileError("We couldn't load your workspace details. Please refresh the page or try again later.");
      return null;
    } finally {
      setProfileLoading(false);
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    if (!isAuthenticated) {
      setProfile(null);
      setProfileError(null);
      setPendingApproval(false);
      return;
    }

    loadProfile().catch(() => {
      /* error already captured in state */
    });
  }, [isAuthenticated, loadProfile]);

  const displayName = profile?.name ?? user?.name ?? user?.email ?? "Account";

  const defaultDashboard = useMemo(() => {
    if (!profile?.role) {
      return null;
    }

    if (profile.role === "vendor") {
      return <VendorDashboard vendorId={profile.vendor_id ?? null} />;
    }

    if (profile.role === "district") {
      const activeDistrictId =
        profile.active_district_id ?? profile.district_id ?? null;
      return (
        <DistrictDashboard
          districtId={activeDistrictId}
          initialMemberships={profile.district_memberships ?? []}
          onMembershipChange={loadProfile}
        />
      );
    }

    if (profile.role === "admin") {
      return <AdminDashboard currentUser={profile} />;
    }

    return null;
  }, [profile, loadProfile]);

  const routedDashboard = (
    <Routes>
      <Route
        path="/"
        element={
          defaultDashboard ?? (
            <div className="text-sm text-slate-600">
              Your account is active, but no dashboards are currently available for your role.
            </div>
          )
        }
      />
      <Route
        path="/admin/users"
        element={profile?.role === "admin" ? <AdminUserDashboard /> : <Navigate to="/" replace />} 
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );

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
  } else if (pendingApproval) {
    mainContent = <PendingApproval />;
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
  } else {
    mainContent = routedDashboard;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Toaster position="top-right" />
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
