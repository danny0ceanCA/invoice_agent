import { useEffect, useState } from "react";

async function loadChatKitModule() {
  try {
    const module = await import(
      /* @vite-ignore */
      "https://cdn.openai.com/chatkit/v1/chatkit.js"
    );
    return module.ChatKit;
  } catch (error) {
    console.error("Failed to load ChatKit module:", error);
    return null;
  }
}

export default function ChatAgent() {
  const [token, setToken] = useState(null);
  const [ChatKitCtor, setChatKitCtor] = useState(null);

  useEffect(() => {
    setToken(localStorage.getItem("access_token"));
  }, []);

  useEffect(() => {
    let active = true;
    loadChatKitModule().then((ctor) => {
      if (active) {
        setChatKitCtor(() => ctor);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  if (!token || !ChatKitCtor) {
    return <div style={{ padding: "1rem", color: "#666" }}>
      Loading assistant…
    </div>;
  }

  const agent = new ChatKitCtor({
    baseUrl: "/api/agents/analytics",
    token: async () => token,
    passThrough: true,
  });

  return (
    <div
      style={{
        height: "600px",
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        padding: "1rem",
        background: "white",
        marginTop: "1.5rem",
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
      }}
    >
      <h3
        style={{
          fontSize: "1.25rem",
          fontWeight: 600,
          marginBottom: "0.5rem",
        }}
      >
        AI Analytics Assistant
      </h3>

      <p
        style={{
          color: "#6b7280",
          fontSize: "0.9rem",
          marginBottom: "1rem",
        }}
      >
        Ask questions about invoices, spending, vendors, or students.
      </p>

      <agent.Chat
        style={{
          height: "100%",
          width: "100%",
          borderRadius: "8px",
        }}
      />
    </div>
  );
}
