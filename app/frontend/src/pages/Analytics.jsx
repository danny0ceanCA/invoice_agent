import { useAuth0 } from "@auth0/auth0-react";
import { useQuery } from "@tanstack/react-query";

import api from "../api";
import ChatAgent from "../components/ChatAgent.jsx";

export default function Analytics() {
  const { isAuthenticated } = useAuth0();

  const { data: district } = useQuery({
    queryKey: ["district-profile"],
    queryFn: async () => {
      const response = await api.get("/api/districts/me");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const districtKey = district?.district_key ?? null;

  return (
    <div className="analytics-page" style={{ padding: "1rem 0" }}>
      <h2
        style={{
          fontSize: "1.5rem",
          fontWeight: 600,
          marginBottom: "1rem",
        }}
      >
        Analytics
      </h2>

      <p
        style={{
          color: "#4b5563",
          maxWidth: "700px",
          marginBottom: "1.5rem",
        }}
      >
        Dive into spending trends, vendor utilization, and budget insights.
        Ask questions using the AI Analytics Assistant to generate reports instantly.
      </p>

      {/* Chat card */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm max-w-[960px] mx-auto">
        <div className="border-b border-slate-100 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-500">
            AI Analytics Assistant
          </p>
          <p className="mt-1 text-sm text-slate-600">
            Ask natural-language questions about invoices, vendors, students, monthly totals, or spending.
          </p>
        </div>
        <div className="px-4 py-4">
          <ChatAgent districtKey={districtKey} />
        </div>
      </div>
    </div>
  );
}
