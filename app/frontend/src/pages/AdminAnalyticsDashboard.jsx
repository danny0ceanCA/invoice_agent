import { useCallback, useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

import {
  fetchAdminCacheEntries,
  fetchAdminMaterializedReports,
  fetchAdminPrefetchHistory,
} from "../api/adminAnalytics";

export default function AdminAnalyticsDashboard() {
  const { getAccessTokenSilently } = useAuth0();
  const [cacheData, setCacheData] = useState(null);
  const [reportsData, setReportsData] = useState(null);
  const [prefetchHistory, setPrefetchHistory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState([]);
  const [expandedReports, setExpandedReports] = useState({});

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setErrors([]);
    try {
      const token = await getAccessTokenSilently();
      const results = await Promise.allSettled([
        fetchAdminCacheEntries(token),
        fetchAdminMaterializedReports(token, { limit: 20 }),
        fetchAdminPrefetchHistory(token),
      ]);

      const nextErrors = [];
      const [cacheResult, reportsResult, prefetchResult] = results;

      if (cacheResult.status === "fulfilled") {
        setCacheData(cacheResult.value);
      } else {
        console.error("admin_cache_fetch_failed", cacheResult.reason);
        setCacheData(null);
        nextErrors.push("Cache entries failed to load.");
      }

      if (reportsResult.status === "fulfilled") {
        setReportsData(reportsResult.value);
      } else {
        console.error("admin_materialized_reports_fetch_failed", reportsResult.reason);
        setReportsData(null);
        nextErrors.push("Materialized reports failed to load.");
      }

      if (prefetchResult.status === "fulfilled") {
        setPrefetchHistory(prefetchResult.value);
      } else {
        console.error("admin_prefetch_history_fetch_failed", prefetchResult.reason);
        setPrefetchHistory(null);
        nextErrors.push("Prefetch history failed to load.");
      }

      setErrors(nextErrors);
    } catch (error) {
      console.error("admin_analytics_load_failed", error);
      setCacheData(null);
      setReportsData(null);
      setPrefetchHistory(null);
      setErrors([
        "We couldn't load admin analytics right now. Please refresh and try again.",
      ]);
    } finally {
      setLoading(false);
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    loadAnalytics().catch(() => {});
  }, [loadAnalytics]);

  const toggleReportPayload = (id) => {
    setExpandedReports((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const cacheItems = cacheData?.items ?? [];
  const materializedItems = reportsData?.items ?? [];
  const prefetchItems = prefetchHistory?.items ?? [];

  return (
    <div className="space-y-6 text-slate-800">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">System Analytics</h2>
          <p className="mt-1 text-sm text-slate-600">
            Inspect cache entries, materialized reports, and prefetch activity for CareSpend Analytics.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading ? <span className="text-xs text-slate-500">Loading admin analytics…</span> : null}
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:bg-slate-50"
            onClick={() => loadAnalytics()}
            disabled={loading}
          >
            Refresh
          </button>
        </div>
      </div>

      {errors.length > 0 ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <p className="font-semibold">Some analytics failed to load</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cache Entries</p>
          <p className="mt-3 text-3xl font-bold text-slate-900">{cacheData?.total_keys ?? "–"}</p>
          <p className="mt-1 text-sm text-slate-600">Redis-backed analytics cache entries.</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Materialized Reports</p>
          <p className="mt-3 text-3xl font-bold text-slate-900">{reportsData?.total ?? "–"}</p>
          <p className="mt-1 text-sm text-slate-600">Persisted analytics reports in Postgres.</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prefetch Jobs</p>
          <p className="mt-3 text-3xl font-bold text-slate-900">{prefetchItems.length ?? "–"}</p>
          <p className="mt-1 text-sm text-slate-600">Most recent prefetch jobs executed by Celery.</p>
        </div>
      </div>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Analytics Cache</h3>
          <span className="text-xs text-slate-500">{cacheItems.length} entries listed</span>
        </div>
        {cacheItems.length === 0 ? (
          <p className="text-sm text-slate-600">No cache entries currently recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3 font-semibold">Key</th>
                  <th className="px-4 py-3 font-semibold">TTL (s)</th>
                  <th className="px-4 py-3 font-semibold">Approx Size (bytes)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {cacheItems.map((entry) => (
                  <tr key={entry.key} className="hover:bg-slate-50">
                    <td className="whitespace-pre-wrap px-4 py-3 font-mono text-xs text-slate-800">{entry.key}</td>
                    <td className="px-4 py-3 text-slate-700">{entry.ttl_seconds ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-700">{entry.approx_bytes ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Materialized Reports</h3>
          <span className="text-xs text-slate-500">{materializedItems.length} records</span>
        </div>
        {materializedItems.length === 0 ? (
          <p className="text-sm text-slate-600">No materialized reports have been created yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3 font-semibold">ID</th>
                  <th className="px-4 py-3 font-semibold">District</th>
                  <th className="px-4 py-3 font-semibold">Kind</th>
                  <th className="px-4 py-3 font-semibold">Entity</th>
                  <th className="px-4 py-3 font-semibold">Created At</th>
                  <th className="px-4 py-3 font-semibold">Last Accessed</th>
                  <th className="px-4 py-3 font-semibold">Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {materializedItems.map((report) => {
                  const createdAt = report.created_at
                    ? new Date(report.created_at).toLocaleString()
                    : "—";
                  const lastAccessed = report.last_accessed_at
                    ? new Date(report.last_accessed_at).toLocaleString()
                    : "—";
                  const isExpanded = expandedReports[report.id];
                  const payloadContent =
                    report.payload_preview || report.payload || null;

                  return (
                    <tr key={report.id} className="align-top hover:bg-slate-50">
                      <td className="px-4 py-3 text-slate-800">{report.id}</td>
                      <td className="px-4 py-3 text-slate-700">{report.district_key || "—"}</td>
                      <td className="px-4 py-3 text-slate-700">{report.report_kind || "—"}</td>
                      <td className="px-4 py-3 text-slate-700">{report.primary_entity || "—"}</td>
                      <td className="px-4 py-3 text-slate-700">{createdAt}</td>
                      <td className="px-4 py-3 text-slate-700">{lastAccessed}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {payloadContent ? (
                          <div className="space-y-2">
                            <button
                              type="button"
                              className="text-sm font-semibold text-indigo-600 hover:text-indigo-700"
                              onClick={() => toggleReportPayload(report.id)}
                            >
                              {isExpanded ? "Hide payload" : "View payload"}
                            </button>
                            {isExpanded ? (
                              <pre className="max-w-xl whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-800">
                                {JSON.stringify(payloadContent, null, 2)}
                              </pre>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-slate-500">No payload</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Prefetch History</h3>
          <span className="text-xs text-slate-500">{prefetchItems.length} entries</span>
        </div>
        {prefetchItems.length === 0 ? (
          <p className="text-sm text-slate-600">No prefetch history recorded yet.</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {prefetchItems.map((entry, index) => (
              <div
                key={`${entry.timestamp || "unknown"}-${index}`}
                className="rounded-lg border border-slate-200 bg-slate-50 p-4 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">District</p>
                    <p className="text-sm font-semibold text-slate-900">{entry.district_key || "—"}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Timestamp</p>
                    <p className="text-sm text-slate-800">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "—"}
                    </p>
                  </div>
                </div>
                <div className="mt-3 text-sm text-slate-700">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Queries</p>
                  <p className="mt-1 whitespace-pre-wrap text-slate-800">
                    {Array.isArray(entry.queries)
                      ? entry.queries.join(", ")
                      : entry.queries || "—"}
                  </p>
                </div>
                {entry.reason ? (
                  <div className="mt-3 text-sm text-slate-700">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Reason</p>
                    <p className="mt-1 text-slate-800">{entry.reason}</p>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
