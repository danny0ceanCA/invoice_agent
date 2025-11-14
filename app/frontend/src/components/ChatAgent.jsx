import { useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

/**
 * Robust CDN loader for ChatKit.
 * - Adds script once (guards by data attribute)
 * - Resolves when window.ChatKit appears
 * - Retries once with type="module" if needed
 */
function loadChatKitFromCdn() {
  const SRC = "https://cdn.openai.com/chatkit/v1/chatkit.js";
  const ATTR = "data-chatkit-cdn";

  function attach({ type }) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[${ATTR}]`);
      if (existing) {
        // If already present, wait a microtick for window.ChatKit
        setTimeout(() => (window.ChatKit ? resolve(window.ChatKit) : resolve(null)), 0);
        return;
      }
      const script = document.createElement("script");
      script.setAttribute(ATTR, "true");
      if (type) script.type = type; // often not needed; leave unset first
      script.async = true;
      script.src = SRC;
      script.onload = () => resolve(window.ChatKit ?? null);
      script.onerror = () => reject(new Error("Failed to load ChatKit CDN script"));
      document.head.appendChild(script);
    });
  }

  return (async () => {
    // First try plain script (global UMD-style)
    try {
      const ctor = await attach({ type: undefined });
      if (ctor) return ctor;
    } catch (e) {
      // swallow; will retry with module
    }
    // Retry with ESM type if global didn’t appear
    try {
      const ctor = await attach({ type: "module" });
      if (ctor) return ctor;
    } catch (e) {
      // give up below
    }
    return null;
  })();
}

export default function ChatAgent() {
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  const [ChatKitCtor, setChatKitCtor] = useState(null);
  const [error, setError] = useState(null);

  // Lazily fetch a valid SPA access token from Auth0 on demand
  const tokenSupplier = useMemo(() => {
    return async () => {
      // Audience is set globally in the Auth0Provider; no args needed here
      return await getAccessTokenSilently();
    };
  }, [getAccessTokenSilently]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const ctor = await loadChatKitFromCdn();
      if (!mounted) return;
      if (!ctor) {
        setError("Failed to load the chat component.");
        return;
      }
      setChatKitCtor(() => ctor);
    })().catch((e) => {
      if (mounted) setError("Failed to initialize the chat component.");
      // eslint-disable-next-line no-console
      console.error(e);
    });
    return () => {
      mounted = false;
    };
  }, []);

  if (!isAuthenticated) {
    return (
      <div className="text-sm text-slate-500">
        Please sign in to use the Analytics Assistant.
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!ChatKitCtor) {
    return <div className="text-sm text-slate-500">Loading assistant…</div>;
  }

  // IMPORTANT: point ChatKit at the working agent endpoint
  const agent = new ChatKitCtor({
    baseUrl: "/api/analytics/agent",
    token: tokenSupplier, // pull fresh SPA token silently
    passThrough: true, // let the backend handle the tools
  });

  const Wrapper = ({ children }) => (
    <div
      style={{
        height: "640px",
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        padding: "1rem",
        background: "white",
        marginTop: "1.25rem",
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
      }}
    >
      {children}
    </div>
  );

  return (
    <Wrapper>
      <agent.Chat />
    </Wrapper>
  );
}
