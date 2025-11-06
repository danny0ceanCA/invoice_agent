import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

import VendorDashboard from "./VendorDashboard.jsx";
import DistrictDashboard from "./DistrictDashboard.jsx";
import { RoleSelection } from "./RoleSelection";
import {
  fetchCurrentUser,
  selectUserRole,
  type CurrentUserResponse,
  type RoleSelectionOption,
} from "../api/auth";

type TabDefinition = {
  key: string;
  label: string;
  roles: ReadonlyArray<"vendor" | "district" | "admin">;
  render: () => JSX.Element;
};

type AvailableTab = {
  key: string;
  label: string;
  component: JSX.Element;
};

export function App() {
  const { isAuthenticated, isLoading, loginWithRedirect, logout, user, getAccessTokenSilently } = useAuth0();
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [profile, setProfile] = useState<CurrentUserResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [isSavingRole, setIsSavingRole] = useState(false);

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
      setActiveTab(null);
      setProfileError(null);
      return;
    }

    loadProfile().catch(() => {
      /* error already captured in state */
    });
  }, [isAuthenticated, loadProfile]);

  const handleRoleSelection = useCallback(
    async (role: RoleSelectionOption) => {
      if (!isAuthenticated) {
        await loginWithRedirect();
        return;
      }

      setIsSavingRole(true);
      setRoleError(null);
      try {
        const token = await getAccessTokenSilently();
        await selectUserRole(token, role);
        await loadProfile();
      } catch (error) {
        console.error("role_assignment_failed", error);
        setRoleError("We couldn't save your selection. Please try again.");
      } finally {
        setIsSavingRole(false);
      }
    },
    [getAccessTokenSilently, isAuthenticated, loadProfile, loginWithRedirect],
  );

  const tabDefinitions = useMemo<TabDefinition[]>(
    () => [
      {
        key: "vendor",
        label: "Vendor",
        roles: ["vendor", "admin"],
        render: () => <VendorDashboard vendorId={profile?.vendor_id ?? null} />,
      },
      {
        key: "district",
        label: "District",
        roles: ["district", "admin"],
        render: () => <DistrictDashboard />,
      },
      {
        key: "admin",
        label: "Admin",
        roles: ["admin"],
        render: () => (
          <div className="text-slate-600">
            Administrative tooling for dataset profiles will land shortly.
          </div>
        ),
      },
    ],
    [profile?.vendor_id],
  );

  const availableTabs = useMemo<AvailableTab[]>(() => {
    if (!profile?.role) {
      return [];
    }

    return tabDefinitions
      .filter((tab) => profile.role === "admin" || tab.roles.includes(profile.role))
      .map((tab) => ({
        key: tab.key,
        label: tab.label,
        component: tab.render(),
      }));
  }, [profile?.role, tabDefinitions]);

  useEffect(() => {
    if (!availableTabs.length) {
      setActiveTab(null);
      return;
    }

    setActiveTab((current) => {
      if (current && availableTabs.some((tab) => tab.key === current)) {
        return current;
      }
      return availableTabs[0]?.key ?? null;
    });
  }, [availableTabs]);

  const activeTabDefinition = useMemo(() => {
    if (!activeTab) {
      return null;
    }
    return availableTabs.find((tab) => tab.key === activeTab) ?? null;
  }, [activeTab, availableTabs]);

  const displayName = profile?.name ?? user?.name ?? user?.email ?? "Account";
  const showNavigation = isAuthenticated && !profile?.needs_role_selection && availableTabs.length > 0;

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
      <RoleSelection onSelect={handleRoleSelection} isSubmitting={isSavingRole} error={roleError} />
    );
  } else if (!profile) {
    mainContent = <div className="text-sm text-slate-600">We couldn't load your profile.</div>;
  } else if (!availableTabs.length || !activeTabDefinition) {
    mainContent = (
      <div className="text-sm text-slate-600">
        Your account is active, but no dashboards are currently available for your role.
      </div>
    );
  } else {
    mainContent = activeTabDefinition.component;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-6 px-6 py-4">
          <h1 className="text-xl font-semibold">ASCS Invoice Automation</h1>
          <div className="flex items-center gap-4">
            {showNavigation ? (
              <nav className="flex gap-2">
                {availableTabs.map((tab) => (
                  <button
                    key={tab.key}
                    className={`rounded px-3 py-1 text-sm font-medium transition hover:bg-slate-100 ${
                      activeTab === tab.key ? "bg-slate-200" : ""
                    }`}
                    onClick={() => setActiveTab(tab.key)}
                    type="button"
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            ) : null}
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
