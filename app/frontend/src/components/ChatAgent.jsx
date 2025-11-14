import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

const CHATKIT_SRC = "https://cdn.openai.com/chatkit/v1/chatkit.js";
const CHATKIT_ATTR = "data-chatkit-loader";
let chatKitPromise = null;

const loadChatKitScript = (type) => {
  if (typeof window === "undefined") {
    return Promise.resolve(null);
  }

  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[${CHATKIT_ATTR}]`);
    if (existing) {
      if (existing.getAttribute("data-loaded") === "true" && window.ChatKit) {
        resolve(window.ChatKit);
        return;
      }

      existing.addEventListener(
        "load",
        () => resolve(window.ChatKit ?? null),
        { once: true },
      );
      existing.addEventListener(
        "error",
        () => reject(new Error("Failed to load ChatKit CDN script")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.setAttribute(CHATKIT_ATTR, "true");
    if (type) {
      script.type = type;
    }
    script.async = true;
    script.src = CHATKIT_SRC;
    script.onload = () => {
      script.setAttribute("data-loaded", "true");
      resolve(window.ChatKit ?? null);
    };
    script.onerror = () => {
      script.remove();
      reject(new Error("Failed to load ChatKit CDN script"));
    };
    document.head.appendChild(script);
  });
};

const removeChatKitScript = () => {
  const existing = document.querySelector(`script[${CHATKIT_ATTR}]`);
  if (existing) {
    existing.remove();
  }
};

function loadChatKitFromCdn() {
  if (typeof window === "undefined") {
    return Promise.resolve(null);
  }

  if (window.ChatKit) {
    return Promise.resolve(window.ChatKit);
  }

  if (chatKitPromise) {
    return chatKitPromise;
  }

  chatKitPromise = (async () => {
    // Try module script first; if it fails, fall back to classic.
    try {
      const moduleCtor = await loadChatKitScript("module");
      if (moduleCtor) {
        return moduleCtor;
      }
    } catch (error) {
      console.warn("chatkit_module_load_failed", error);
    }

    removeChatKitScript();

    try {
      const classicCtor = await loadChatKitScript();
      if (classicCtor) {
        return classicCtor;
      }
    } catch (error) {
      console.error("chatkit_classic_load_failed", error);
    }

    return window.ChatKit ?? null;
  })();

  return chatKitPromise.finally(() => {
    chatKitPromise = null;
  });
}

function FallbackChat({ tokenSupplier, notice, districtKey }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm the built-in analytics assistant. Ask about invoices, vendors, students, or spending totals.",
      html: null,
      rows: null,
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestError, setRequestError] = useState(null);
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const query = inputValue.trim();
    if (!query || isSubmitting) {
      return;
    }

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setInputValue("");
    setIsSubmitting(true);
    setRequestError(null);

    try {
      const token = await tokenSupplier();
      const response = await fetch("/api/agents/analytics", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query,
          context: {
            district_key: districtKey || null,
          },
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Request failed with status ${response.status}`);
      }

      let assistantMessage = "";
      let htmlSnippet = null;
      let rows = null;
      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        const data = await response.json();
        if (data && typeof data === "object" && !Array.isArray(data)) {
          if (typeof data.html === "string") {
            htmlSnippet = data.html;
          }
          if (Array.isArray(data.rows)) {
            rows = data.rows;
          }
          const summary =
            data?.answer ??
            data?.message ??
            data?.response ??
            data?.summary ??
            data?.text ??
            "";
          assistantMessage = typeof summary === "string" ? summary : "";
        } else if (typeof data === "string") {
          assistantMessage = data;
        } else {
          assistantMessage = JSON.stringify(data, null, 2);
        }
      } else {
        assistantMessage = await response.text();
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          // Only store the summary text; HTML will be rendered separately
          content:
            typeof assistantMessage === "string" && assistantMessage.trim()
              ? assistantMessage
              : "I sent a response, but it was empty.",
          html: htmlSnippet,
          rows: Array.isArray(rows) ? rows : null,
        },
      ]);
    } catch (error) {
      const friendlyMessage =
        error instanceof Error ? error.message : "We couldn't reach the analytics assistant.";
      setRequestError(friendlyMessage);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ ${friendlyMessage}`,
          html: null,
          rows: null,
        },
      ]);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {notice ? (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
          {notice}
        </div>
      ) : null}

      <div
        ref={scrollContainerRef}
        className="flex-1 min-h-0 space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-4"
      >
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`max-w-full rounded-xl px-4 py-3 text-sm leading-relaxed ${
              message.role === "user"
                ? "ml-auto bg-amber-500 text-white"
                : "mr-auto bg-white text-slate-700 shadow"
            }`}
          >
            <div className="whitespace-pre-wrap">{message.content}</div>
            {message.html ? (
              <div
                className="mt-2 overflow-x-auto text-xs text-slate-700"
                dangerouslySetInnerHTML={{ __html: message.html }}
              />
            ) : null}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex items-center gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          placeholder="Ask a question about invoices, vendors, or spending…"
          disabled={isSubmitting}
        />
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Sending…" : "Send"}
        </button>
      </form>

      {requestError ? (
        <p className="mt-2 text-xs text-amber-600">
          {requestError} — we are continuing to use the fallback assistant.
        </p>
      ) : null}
    </div>
  );
}

export default function ChatAgent({ districtKey }) {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  const [ChatKitCtor, setChatKitCtor] = useState(null);
  const [isFallbackActive, setIsFallbackActive] = useState(false);
  const [fallbackNotice, setFallbackNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const tokenSupplier = useMemo(() => {
    return async () => {
      try {
        // If the SPA session hasn't finished loading, return empty string so ChatKit retries on interaction.
        if (isLoading || !isAuthenticated) return "";
        const token = await getAccessTokenSilently();
        return token || "";
      } catch (e) {
        console.error("chatkit_token_failed", e);
        return "";
      }
    };
  }, [getAccessTokenSilently, isAuthenticated, isLoading]);

  useEffect(() => {
    let isMounted = true;
    loadChatKitFromCdn()
      .then((ctor) => {
        if (!isMounted) {
          return;
        }
        if (ctor?.Chat) {
          setChatKitCtor(() => ctor);
          setIsFallbackActive(false);
          setFallbackNotice(null);
        } else {
          setIsFallbackActive(true);
          setFallbackNotice(
            "The hosted chat widget is unavailable, but the fallback assistant is ready to help.",
          );
        }
      })
      .catch((error) => {
        console.error("chatkit_load_failed", error);
        if (!isMounted) {
          return;
        }
        setIsFallbackActive(true);
        setFallbackNotice(
          "We couldn't load the hosted chat widget. The fallback assistant is ready below.",
        );
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const agentInstance = useMemo(() => {
    if (!ChatKitCtor?.Chat) {
      return null;
    }

    return new ChatKitCtor({
      baseUrl: "/api/agents/analytics",
      token: tokenSupplier,
      passThrough: true,
    });
  }, [ChatKitCtor, tokenSupplier]);

  const ChatComponent = agentInstance?.Chat ?? null;

  const containerClassName =
    "flex h-[600px] flex-col rounded-2xl border border-slate-200 bg-white shadow-md";

  if (!isAuthenticated) {
    return (
      <div className={containerClassName}>
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
          Please sign in to use the Analytics Assistant.
        </div>
      </div>
    );
  }

  if (ChatComponent && !isFallbackActive) {
    return (
      <div className={containerClassName}>
        <div className="border-b border-slate-200 px-4 py-2">
          <h3 className="text-sm font-semibold text-slate-900">AI Analytics Assistant</h3>
          <p className="text-xs text-slate-500">
            Ask about invoices, vendors, students, service months, and spending.
          </p>
        </div>
        <div className="flex-1 min-h-0 overflow-hidden">
          {/* ChatKit manages its own scroll inside this area */}
          <ChatComponent />
        </div>
      </div>
    );
  }

  if (isLoading && !isFallbackActive) {
    return (
      <div className={containerClassName}>
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
          Loading assistant…
        </div>
      </div>
    );
  }

  return (
    <div className={containerClassName}>
      <div className="border-b border-slate-200 px-4 py-2">
        <h3 className="text-sm font-semibold text-slate-900">AI Analytics Assistant</h3>
        <p className="text-xs text-slate-500">
          Ask about invoices, vendors, students, service months, and spending.
        </p>
      </div>
      <div className="flex-1 min-h-0 p-4">
        <FallbackChat
          tokenSupplier={tokenSupplier}
          notice={fallbackNotice}
          districtKey={districtKey}
        />
      </div>
    </div>
  );
}
