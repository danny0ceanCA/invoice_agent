import { useEffect, useState } from "react";
import { ChatKit } from "@openai/chatkit";

export default function ChatAgent() {
  const [token, setToken] = useState(null);

  useEffect(() => {
    const t = localStorage.getItem("access_token");
    setToken(t);
  }, []);

  if (!token) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#6b7280" }}>
        Loading assistant...
      </div>
    );
  }

  const agent = new ChatKit({
    baseUrl: "/api/agents/analytics",
    token: async () => token,
    passThrough: true,
  });

  return (
    <>
      <h3
        style={{
          fontSize: "1.25rem",
          fontWeight: "600",
          marginBottom: "0.5rem",
        }}
      >
        AI Analytics Assistant
      </h3>

      <p
        style={{
          color: "#6b7280",
          marginBottom: "1rem",
          fontSize: "0.9rem",
        }}
      >
        Ask natural-language questions about spending, invoices, vendors, or students.
      </p>

      <div
        style={{
          height: "600px",
          border: "1px solid #e5e7eb",
          borderRadius: "12px",
          marginTop: "2rem",
          padding: "1rem",
          background: "white",
          boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
        }}
      >
        <agent.Chat
          style={{
            height: "100%",
            width: "100%",
            borderRadius: "8px",
          }}
        />
      </div>
    </>
  );
}
