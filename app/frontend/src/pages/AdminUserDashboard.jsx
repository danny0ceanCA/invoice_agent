import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";

import {
  approveUser,
  deactivateUser,
  listPendingUsers,
  listUsers,
  updateUserRole,
} from "../api/adminUsers";

const TABS = [
  { id: "all", label: "All Users" },
  { id: "pending", label: "Pending" },
  { id: "deactivated", label: "Deactivated" },
];

const ROLE_OPTIONS = [
  { value: "admin", label: "Admin" },
  { value: "vendor", label: "Vendor" },
  { value: "district", label: "District" },
];

export default function AdminUserDashboard() {
  const { getAccessTokenSilently } = useAuth0();
  const [users, setUsers] = useState([]);
  const [pendingUsers, setPendingUsers] = useState([]);
  const [activeTab, setActiveTab] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyUserIds, setBusyUserIds] = useState([]);

  const isUserBusy = useCallback(
    (userId) => busyUserIds.includes(userId),
    [busyUserIds],
  );

  const updateBusyState = useCallback((userId, busy) => {
    setBusyUserIds((prev) => {
      const next = new Set(prev);
      if (busy) {
        next.add(userId);
      } else {
        next.delete(userId);
      }
      return Array.from(next);
    });
  }, []);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessTokenSilently();
      const [usersResponse, pendingResponse] = await Promise.all([
        listUsers(token),
        listPendingUsers(token),
      ]);
      setUsers(usersResponse);
      setPendingUsers(pendingResponse);
    } catch (err) {
      console.error("admin_users_load_failed", err);
      setError("We couldn't load user accounts. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    loadUsers().catch(() => {
      /* handled in loadUsers */
    });
  }, [loadUsers]);

  const displayedUsers = useMemo(() => {
    if (activeTab === "pending") {
      return pendingUsers;
    }
    if (activeTab === "deactivated") {
      return users.filter((user) => user.is_active === false);
    }
    return users;
  }, [activeTab, pendingUsers, users]);

  const handleApprove = async (userId) => {
    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);

    const previousUsers = [...users];
    const previousPending = [...pendingUsers];

    setUsers((current) =>
      current.map((user) =>
        user.id === userId
          ? { ...user, is_approved: true, is_active: true }
          : user,
      ),
    );
    setPendingUsers((current) => current.filter((user) => user.id !== userId));

    try {
      await approveUser(userId, token);
      toast.success("User approved");
    } catch (err) {
      console.error("user_approve_failed", err);
      toast.error("We couldn't approve the user. Please try again.");
      setUsers(previousUsers);
      setPendingUsers(previousPending);
    } finally {
      updateBusyState(userId, false);
    }
  };

  const handleRoleChange = async (userId, role) => {
    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);

    const previousUsers = [...users];
    setUsers((current) =>
      current.map((user) =>
        user.id === userId
          ? { ...user, role }
          : user,
      ),
    );

    try {
      await updateUserRole(userId, role, token);
      toast.success("Role updated");
    } catch (err) {
      console.error("user_role_update_failed", err);
      toast.error("We couldn't update the role. Please try again.");
      setUsers(previousUsers);
    } finally {
      updateBusyState(userId, false);
    }
  };

  const handleDeactivate = async (userId) => {
    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);

    try {
      const response = await deactivateUser(userId, token);
      setUsers((current) =>
        current.map((user) =>
          user.id === userId
            ? { ...user, is_active: response.is_active }
            : user,
        ),
      );
      toast.success("User deactivated");
    } catch (err) {
      console.error("user_deactivate_failed", err);
      toast.error("We couldn't deactivate the user. Please try again.");
    } finally {
      updateBusyState(userId, false);
    }
  };

  return (
    <div className="space-y-6 text-slate-700">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
            aria-label="Return to the admin console"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to Admin Console
          </Link>
          <button
            type="button"
            onClick={() => loadUsers()}
            className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
            aria-label="Refresh user list"
          >
            Refresh
          </button>
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">User Management</h2>
          <p className="text-sm text-slate-600">
            Approve pending accounts, assign roles, and deactivate access for your organization.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              activeTab === tab.id
                ? "bg-slate-900 text-white shadow"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
            aria-pressed={activeTab === tab.id}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
        aria-busy={loading || busyUserIds.length > 0}
      >
        {(loading || busyUserIds.length > 0) && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 backdrop-blur-sm"
            aria-hidden={loading ? undefined : "true"}
          >
            <svg
              className="h-8 w-8 animate-spin text-indigo-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              role="presentation"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              ></path>
            </svg>
          </div>
        )}

        {error ? (
          <div className="text-sm text-red-600">{error}</div>
        ) : displayedUsers.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-center text-sm text-slate-500">
            {activeTab === "pending" ? "No pending users 🎉" : "No users found for this filter."}
          </div>
        ) : (
          <table className="w-full border-separate border-spacing-y-2 text-left">
            <thead>
              <tr className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="rounded-l-lg bg-slate-50 px-4 py-2">Email</th>
                <th className="bg-slate-50 px-4 py-2">Role</th>
                <th className="bg-slate-50 px-4 py-2">Approved</th>
                <th className="bg-slate-50 px-4 py-2">Active</th>
                <th className="rounded-r-lg bg-slate-50 px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayedUsers.map((user) => (
                <tr key={user.id} className="rounded-lg bg-white shadow-sm">
                  <td className="rounded-l-lg px-4 py-3 text-sm font-medium text-slate-900">{user.email}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    <label className="sr-only" htmlFor={`role-${user.id}`}>
                      Change role for {user.email}
                    </label>
                    <select
                      id={`role-${user.id}`}
                      className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                      value={user.role ?? ""}
                      onChange={(event) => {
                        const nextRole = event.target.value;
                        if (nextRole && nextRole !== user.role) {
                          handleRoleChange(user.id, nextRole).catch(() => {});
                        }
                      }}
                      disabled={isUserBusy(user.id)}
                      aria-label={`Change role for ${user.email}`}
                    >
                      <option value="" disabled>
                        Select role
                      </option>
                      {ROLE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {user.is_approved ? (
                      <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                        Approved
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                        Pending
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {user.is_active ? (
                      <span className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="flex flex-wrap items-center justify-end gap-2 rounded-r-lg px-4 py-3 text-sm">
                    {!user.is_approved && (
                      <button
                        type="button"
                        onClick={() => handleApprove(user.id)}
                        className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                        disabled={isUserBusy(user.id)}
                        aria-label={`Approve ${user.email}`}
                      >
                        Approve
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDeactivate(user.id)}
                      className="rounded-lg border border-red-500 px-3 py-2 text-sm font-semibold text-red-600 transition hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2"
                      disabled={isUserBusy(user.id) || !user.is_active}
                      aria-label={`Deactivate ${user.email}`}
                    >
                      Deactivate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

