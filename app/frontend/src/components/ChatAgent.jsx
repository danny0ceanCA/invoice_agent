import { useEffect, useState } from "react";

const CHATKIT_SCRIPT_URL = "https://cdn.openai.com/chatkit/v1/chatkit.js";

function loadChatKitScript() {
  return new Promise((resolve, reject) => {
    // If ChatKit already loaded
    if (window.ChatKit) {
      resolve(window.ChatKit);
      return;
    }

    // Check if script exists
    const existing = document.querySelector("script[data-chatkit]");
    if (existing) {
      existing.addEventListener("load", () => resolve(window.ChatKit));
      existing.addEventListener("error", () =>
        reject(new Error("Failed to load ChatKit script."))
      );
      return;
    }

    const script = document.createElement("script");
    script.src = CHATKIT_SCRIPT_URL;
    script.type = "module";
    script.async = true;
    script.dataset.chatkit = "true";

    script.onload = () => resolve(window.ChatKit);
    script.onerror = () =>
      reject(new Error("Failed to load ChatKit script."));

    document.head.appendChild(script);
  });
}

export default function ChatAgent() {
  const [token, setToken] = useState(null);
  const [ChatKitCtor, setChatKitCtor] = useState(null);

  useEffect(() => {
    setToken(localStorage.getItem("access_token"));
  }, []);

  useEffect(() => {
    let active = true;
    loadChatKitScript()
      .then((ctor) => {
        if (active) setChatKitCtor(() => ctor);
      })
      .catch((err) => console.error("ChatKit load error:", err));

    return () => (active = false);
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
