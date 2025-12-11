import React from "react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

// Backend API base URL (Render: VITE_API_BASE_URL, Dev: fallback to /api)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const PAGE_SESSION_ID = crypto.randomUUID();

function formatTimingHtml(timings) {
  if (!timings || typeof timings !== "object") return null;

  const total =
    typeof timings.total_seconds === "number"
      ? Number(timings.total_seconds).toFixed(2)
      : null;

  const stageEntries =
    timings.stages && typeof timings.stages === "object"
      ? Object.entries(timings.stages).filter(
          ([, value]) => typeof value === "number"
        )
      : [];

  if (!total && stageEntries.length === 0) return null;

  const listItems = stageEntries
    .map(
      ([name, value]) =>
        `<li><span class="font-semibold">${name}</span>: ${Number(value).toFixed(
          2
        )}s</li>`
    )
    .join("");

  const stagesHtml =
    listItems.length > 0
      ? `<ul class="mt-1 list-disc pl-4 text-[13px] text-slate-600">${listItems}</ul>`
      : "";

  const totalText = total ? `Total response time: ${total}s` : "Response timing";
  return `<div class="text-xs text-slate-600">${totalText}${stagesHtml}</div>`;
}

function ChatAgent({ districtKey }) {
  console.log("ChatAgent using districtKey:", districtKey);
  const { isAuthenticated, isLoading, getAccessTokenSilently } = useAuth0();

  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm your analytics assistant. Ask about invoices, students, vendors, months, or totals.",
    },
  ]);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [token, setToken] = useState("");
  const scrollRef = useRef(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll chat window
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      setShowScrollButton(false);
    }
  }, [messages]);

  // Acquire Auth0 token ONCE when authenticated
  useEffect(() => {
    async function loadToken() {
      if (isLoading) return;
      if (!isAuthenticated) return;
      try {
        const t = await getAccessTokenSilently();
        if (t && t !== token) setToken(t);
      } catch (err) {
        console.error("Auth0 token load failed:", err);
      }
    }
    loadToken();
  }, [isLoading, isAuthenticated, getAccessTokenSilently, token]);

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const text = input.trim();
    setInput("");

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);

    try {
      if (!isAuthenticated) {
        throw new Error("Please sign in to use the analytics assistant.");
      }
      if (!token) {
        throw new Error("Authentication is initializing… please retry.");
      }

      console.log("Sending analytics payload:", {
        query: text,
        district_key: districtKey,
      });

      const res = await fetch(`${API_BASE_URL}/agents/analytics`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query: text,
          district_key: districtKey ?? null,
          context: {
            district_key: districtKey ?? null,
            session_id: PAGE_SESSION_ID,
          },
        }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(
          data?.detail ||
            data?.error ||
            data?.message ||
            `Analytics error (HTTP ${res.status})`
        );
      }

      const safeHtml =
        typeof data?.html === "string" && data.html.trim().length
          ? data.html
          : `<p>${(data?.text || "").replace(/</g, "&lt;")}</p>`;
      const timingHtml = formatTimingHtml(data?.timings);

      setMessages((prev) => {
        const next = [...prev, { role: "assistant", content: safeHtml, html: true }];
        if (timingHtml) {
          next.push({ role: "assistant", content: timingHtml, html: true });
        }
        return next;
      });
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Unexpected analytics error.";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `<p>${msg.replace(/</g, "&lt;")}</p>`,
          html: true,
        },
      ]);
    }

    setSending(false);
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center text-slate-600">
        Loading assistant…
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="h-full flex items-center justify-center text-slate-600">
        Please sign in to use the Analytics Assistant.
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col bg-white">
      {/* Scrollable chat area */}
      <div
        ref={scrollRef}
        className="px-4 py-4 space-y-4"
        onScroll={(e) => {
          const target = e.target;
          const atBottom =
            target.scrollHeight - target.scrollTop <= target.clientHeight + 20;
          setShowScrollButton(!atBottom);
        }}
      >
        {messages.map((m, i) => {
          console.log("MSG", m);
          return (
            <div
              key={i}
              className={`
                block
                w-full
                sm:max-w-[75%]
                md:max-w-[65%]
                lg:max-w-[55%]
                xl:max-w-[50%]
                rounded-2xl
                overflow-hidden
                break-words
                [overflow-wrap:anywhere]
                whitespace-normal
                min-w-0
                ${
                  m.role === "user"
                    ? `
                        bg-amber-500 text-white ml-auto
                        shadow-lg shadow-amber-300/30
                        rounded-2xl
                        px-6 py-4
                        max-w-[85%]
                        text-[1rem]
                        leading-relaxed
                      `
                    : `
                        bg-slate-100 text-slate-800 mr-auto
                        shadow-md
                        rounded-2xl
                        px-6 py-4
                        max-w-[85%]
                      `
                }
              `}
            >
              {m.html ? (
                <div
                  className="
                  max-h-80
                  w-full
                  max-w-full
                  overflow-y-auto
                  overflow-x-auto
                  break-words
                  [overflow-wrap:anywhere]
                  whitespace-normal
                  prose
                  prose-sm
                  prose-ul:pl-5
                  prose-li:break-words
                  [&_li]:break-words
                  [&_ul]:list-disc
                  [&_ol]:list-decimal
                  [&_p]:break-words
                  [&_p]:[overflow-wrap:anywhere]
                  [&_span]:break-words
                  [&_span]:[overflow-wrap:anywhere]
                  [&_a]:break-words
                  [&_a]:[overflow-wrap:anywhere]
                  table-auto
                  prose-table:table-fixed
                  [&_table]:block
                  [&_table]:max-w-full
                  [&_table]:overflow-y-auto
                  prose-th:break-words
                  prose-td:break-words
                  prose-td:whitespace-normal
                  prose-pre:whitespace-pre-wrap
                  prose-pre:break-words
                  prose-pre:overflow-auto
                  prose-img:max-w-full
                  prose-img:h-auto
                  [&_*]:max-w-full
                  [&_table]:border-collapse
                  [&_th]:text-left
                  [&_th]:align-top
                  [&_td]:align-top
                  max-w-full
                "
                dangerouslySetInnerHTML={{ __html: m.content }}
                />
              ) : (
                <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                  {m.content}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {showScrollButton && (
        <button
          onClick={() => {
            const el = scrollRef.current;
            if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
          }}
          className="absolute bottom-20 right-8 bg-amber-500 text-white px-3 py-2 text-xs rounded-full shadow-lg hover:bg-amber-600 transition"
        >
          ↓ Scroll to bottom
        </button>
      )}

      {/* Input bar with Home button */}
      <div className="border-t border-slate-200 p-3 bg-white min-w-0">
        <div className="flex gap-3 items-center">
          <form onSubmit={handleSend} className="flex gap-3 flex-1">
            <input
              type="text"
              className="flex-1 min-w-0 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-400"
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
          <Link
            to="/"
            className="inline-flex items-center rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Home
          </Link>
        </div>
      </div>
    </div>
  );
}

export default React.memo(ChatAgent);
