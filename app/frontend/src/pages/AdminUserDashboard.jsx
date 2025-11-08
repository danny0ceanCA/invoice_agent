import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import toast from "react-hot-toast";

import {
  approveUser,
  deactivateUser,
  declineUser,
  listPendingUsers,
  listUsers,
  updateUserRole,
} from "../api/adminUsers";

function normalizeUserShape(user) {
  if (!user) return user;
  const isApproved = user.is_approved ?? user.approved ?? false;
  const isActive = user.is_active ?? user.active ?? false;
  const vendorCompany = user.vendor_company_name ?? user.vendorCompanyName ?? null;
  const districtCompany = user.district_company_name ?? user.districtCompanyName ?? null;
  return {
    ...user,
    is_approved: isApproved,
    is_active: isActive,
    vendor_company_name: vendorCompany,
    district_company_name: districtCompany,
  };
}

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
    [busyUserIds]
  );

  const updateBusyState = useCallback((userId, busy) => {
    setBusyUserIds((prev) => {
      const next = new Set(prev);
      busy ? next.add(userId) : next.delete(userId);
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
      setUsers(usersResponse.map(normalizeUserShape));
      setPendingUsers(pendingResponse.map(normalizeUserShape));
    } catch (err) {
      console.error("admin_users_load_failed", err);
      setError("We couldn't load user accounts. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    loadUsers().catch(() => {});
  }, [loadUsers]);

  const displayedUsers = useMemo(() => {
    if (activeTab === "pending") return pendingUsers;
    if (activeTab === "deactivated")
      return users.filter((user) => user.is_active === false);

    const combinedUsers = [...users];
    const knownUserIds = new Set(combinedUsers.map((u) => u.id));
    pendingUsers.forEach((p) => {
      if (!knownUserIds.has(p.id)) combinedUsers.push(p);
    });
    return combinedUsers;
  }, [activeTab, pendingUsers, users]);

  const handleApprove = async (userId) => {
    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);
    try {
      const { user: approvedUser } = await approveUser(userId, token);
      const normalized = normalizeUserShape(approvedUser);
      setUsers((current) =>
        current.map((u) =>
          u.id === userId
            ? { ...u, ...normalized, is_approved: true, is_active: true }
            : u
        )
      );
      setPendingUsers((current) => current.filter((u) => u.id !== userId));
      toast.success("User approved successfully");
    } catch (err) {
      console.error("user_approve_failed", err);
      toast.error("We couldn't approve the user. Please try again.");
    } finally {
      updateBusyState(userId, false);
    }
  };

  const handleRoleChange = async (userId, role) => {
    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);
    const prev = [...users];
    setUsers((current) =>
      current.map((u) => (u.id === userId ? { ...u, role } : u))
    );
    try {
      await updateUserRole(userId, role, token);
      toast.success("Role updated");
    } catch (err) {
      console.error("user_role_update_failed", err);
      toast.error("We couldn't update the role. Please try again.");
      setUsers(prev);
    } finally {
      updateBusyState(userId, false);
    }
  };

  const handleDeactivate = async (userId) => {
    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);
    try {
      const response = await deactivateUser(userId, token);
      const normalized = normalizeUserShape(response);
      setUsers((current) =>
        current.map((u) =>
          u.id === userId ? { ...u, is_active: normalized?.is_active ?? false } : u
        )
      );
      toast.success("User deactivated");
    } catch (err) {
      console.error("user_deactivate_failed", err);
      toast.error("We couldn't deactivate the user. Please try again.");
    } finally {
      updateBusyState(userId, false);
    }
  };

  const handleDecline = async (userId) => {
    const confirmed = window.confirm(
      "Are you sure you want to decline this user?"
    );
    if (!confirmed) return;

    const token = await getAccessTokenSilently();
    updateBusyState(userId, true);
    try {
      const { user: declinedUser, message } = await declineUser(userId, token);
      const normalized = normalizeUserShape(declinedUser);
      setUsers((current) =>
        current.map((u) =>
          u.id === userId
            ? { ...u, is_active: normalized?.is_active ?? false, is_approved: false }
            : u
        )
      );
      setPendingUsers((current) => current.filter((u) => u.id !== userId));
      toast.success(message ?? "User declined successfully.");
    } catch (err) {
      console.error("user_decline_failed", err);
      toast.error("We couldn't decline the user. Please try again.");
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
          >
            <ArrowLeft className="h-4 w-4" /> Back to Admin Console
          </Link>
          <button
            type="button"
            onClick={() => loadUsers()}
            className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
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
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        {loading ? (
          <div className="text-center text-slate-500 py-8">Loading users...</div>
        ) : error ? (
          <div className="text-sm text-red-600">{error}</div>
        ) : displayedUsers.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-center text-sm text-slate-500">
            {activeTab === "pending" ? "No pending users 🎉" : "No users found for this filter."}
          </div>
        ) : (
          <table className="w-full border-separate border-spacing-y-2 text-left">
            <thead>
              <tr className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="rounded-l-lg bg-slate-50 px-4 py-2">Account</th>
                <th className="bg-slate-50 px-4 py-2">Company</th>
                <th className="bg-slate-50 px-4 py-2">Role</th>
                <th className="bg-slate-50 px-4 py-2">Approved</th>
                <th className="bg-slate-50 px-4 py-2">Active</th>
                <th className="rounded-r-lg bg-slate-50 px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayedUsers.map((user) => {
                const isApproved = Boolean(user.is_approved);
                const isActive = Boolean(user.is_active);
                const isBusy = isUserBusy(user.id);
                const hasVendorCompany = Boolean(user.vendor_company_name);
                const hasDistrictCompany = Boolean(user.district_company_name);

                return (
                  <tr key={user.id} className="rounded-lg bg-white shadow-sm">
                    <td className="rounded-l-lg px-4 py-3 text-sm font-medium text-slate-900">
                      <div className="space-y-1">
                        <p className="font-semibold text-slate-900">{user.email}</p>
                        {user.name ? (
                          <p className="text-xs font-normal text-slate-500">{user.name}</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      <div className="space-y-2">
                        {hasVendorCompany ? (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-widest text-emerald-600">
                              Vendor
                            </span>
                            <span className="text-sm font-medium text-slate-700">{user.vendor_company_name}</span>
                          </div>
                        ) : null}
                        {hasDistrictCompany ? (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-widest text-sky-600">
                              District
                            </span>
                            <span className="text-sm font-medium text-slate-700">{user.district_company_name}</span>
                          </div>
                        ) : null}
                        {!hasVendorCompany && !hasDistrictCompany ? (
                          <p className="text-xs text-slate-400">No company linked</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      <select
                        id={`role-${user.id}`}
                        className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                        value={user.role ?? ""}
                        onChange={(e) => {
                          const nextRole = e.target.value;
                          if (nextRole && nextRole !== user.role)
                            handleRoleChange(user.id, nextRole).catch(() => {});
                        }}
                        disabled={isBusy}
                      >
                        <option value="" disabled>
                          Select role
                        </option>
                        {ROLE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {isApproved ? (
                        <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                          Approved
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                          Pending Approval
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {isActive ? (
                        <span className="inline-flex items-center rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                          Inactive
                        </span>
                      )}
                    </td>

                    {/* ACTIONS */}
                    <td className="flex justify-end items-center gap-3 px-4 py-3 rounded-r-lg bg-white">
                      {isApproved ? (
                        <button
                          type="button"
                          onClick={() => handleDeactivate(user.id)}
                          className="inline-flex items-center justify-center font-bold px-3 py-2 rounded-md shadow-md border transition-colors !bg-red-600 hover:!bg-red-700 !text-white !border-red-700"
                          style={{ backgroundColor: "#dc2626", color: "#fff" }}
                          disabled={isBusy || !isActive}
                        >
                          Deactivate
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => handleApprove(user.id)}
                            className="inline-flex items-center justify-center font-bold px-3 py-2 rounded-md shadow-md border transition-colors !bg-green-600 hover:!bg-green-700 !text-white !border-green-700"
                            style={{ backgroundColor: "#16a34a", color: "#fff" }}
                            disabled={isBusy}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDecline(user.id)}
                            className="inline-flex items-center justify-center font-bold px-3 py-2 rounded-md shadow-md border transition-colors !bg-red-600 hover:!bg-red-700 !text-white !border-red-700"
                            style={{ backgroundColor: "#dc2626", color: "#fff" }}
                            disabled={isBusy}
                          >
                            Decline
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
