import { useEffect, useRef, useState } from "react";

export default function ChatAgent() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm your analytics assistant. Ask about invoices, students, vendors, months, or totals.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll chat
  useEffect(() => {
    const container = scrollRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [messages]);

  async function sendMessage(e) {
    e.preventDefault();
    if (!input.trim()) return;

    const text = input.trim();
    setInput("");

    // Add user message to UI
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);

    try {
      const res = await fetch("/api/agents/analytics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }),
      });

      const data = await res.json();

      // Use text + html from agent
      const combined =
        data.html && data.html.includes("<table>")
          ? data.html
          : `<p>${data.text}</p>`;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: combined, html: true },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "<p>Sorry — I couldn't reach the analytics agent. Please try again.</p>",
          html: true,
        },
      ]);
    }

    setSending(false);
  }

  return (
    <div
      className="rounded-xl border border-slate-300 p-4 bg-white shadow"
      style={{ height: "600px", display: "flex", flexDirection: "column" }}
    >
      {/* Chat scroll area */}
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
            dangerouslySetInnerHTML={
              m.html ? { __html: m.content } : undefined
            }
          >
            {!m.html ? m.content : null}
          </div>
        ))}
      </div>

      {/* Input bar */}
      <form onSubmit={sendMessage} className="mt-3 flex gap-2">
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
