import { useEffect, useRef, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

export default function ChatAgent() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  const [messages, setMessages] = useResilientMessages();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    const container = scrollRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    // Add user message immediately
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);

    try {
      if (!isAuthenticated) {
        throw new Error("You must be signed in to use the analytics assistant.");
      }

      let token = "";
      try {
        token = await getAccessTokenSilently();
      } catch (err) {
        console.error("Failed to get access token for analytics agent:", err);
        throw new Error("Authentication error. Please refresh and try again.");
      }

      const res = await fetch("/api/agents/analytics", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: token ? `Bearer ${token}` : "",
        },
        body: JSON.stringify({ query: text }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const msg =
          (data && (data.detail || data.error || data.message)) ||
          `Analytics agent error (status ${res.status}).`;
        throw new Error(msg);
      }

      // Expecting shape: { text: string, html: string, rows?: [...] }
      const safeText =
        typeof data?.text === "string" && data.text.trim().length
          ? data.text
          : "";
      const safeHtml =
        typeof data?.html === "string" && data.html.trim().length
          ? data.html
          : safeText
          ? `<p>${escapeHtml(safeText)}</p>`
          : "<p>(No details returned.)</p>";

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: safeHtml,
          html: true,
        },
      ]);
    } catch (err) {
      console.error("analytics_chat_error", err);
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Something went wrong while calling the analytics agent.";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `<p>${escapeHtml(msg)}</p>`,
          html: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  if (!isAuthenticated) {
    return (
      <div
        className="rounded-xl border border-slate-300 p-4 bg-white shadow"
        style={{ height: "600px", display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <p className="text-sm text-slate-600">
          Please sign in to use the Analytics Assistant.
        </p>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl border border-slate-300 p-4 bg-white shadow"
      style={{ height: "600px", display: "flex", flexDirection: "column" }}
    >
      {/* Scrollable chat area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-4 pr-2"
        style={{ paddingRight: "4px" }}
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[80%] px-4 py-2 rounded-xl ${
              m.role === "user"
                ? "bg-amber-500 text-white ml-auto"
                : "bg-slate-100 text-slate-800 mr-auto shadow"
            }`}
          >
            {m.html ? (
              <div
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: m.content }}
              />
            ) : (
              <span>{m.content}</span>
            )}
          </div>
        ))}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSend} className="mt-3 flex gap-2">
        <input
          type="text"
          className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-400"
          placeholder="Ask a question about invoices…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
        />
        <button
          type="submit"
          disabled={sending}
          className="bg-amber-500 text-white px-4 py-2 rounded-lg text-sm font-semibold shadow hover:bg-amber-600 disabled:opacity-50"
        >
          {sending ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}

/**
 * Escape plain text when we need to embed it into HTML safely.
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Custom hook to keep the initial assistant greeting without crashing on reload.
 */
function useResilientMessages() {
  const [messages, setMessages] = useState(() => [
    {
      role: "assistant",
      content:
        "Hello! I'm your analytics assistant. Ask about invoices, students, vendors, months, or totals.",
    },
  ]);
  return [messages, setMessages];
}
