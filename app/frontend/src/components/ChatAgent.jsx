import { useEffect, useMemo, useState } from "react";

const CHATKIT_SCRIPT_URL = "https://cdn.openai.com/chatkit/v1/chatkit.js";

const scriptState = {
  status: typeof window !== "undefined" && window.ChatKit ? "loaded" : "idle",
  promise: null,
};

function loadChatKit() {
  if (scriptState.status === "loaded") {
    return Promise.resolve(window.ChatKit);
  }

  if (scriptState.status === "loading" && scriptState.promise) {
    return scriptState.promise;
  }

  scriptState.status = "loading";
  scriptState.promise = new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("ChatKit is only available in the browser."));
      return;
    }

    const existing = document.querySelector("script[data-chatkit]");
    if (existing && window.ChatKit) {
      scriptState.status = "loaded";
      resolve(window.ChatKit);
      return;
    }

    const script = existing ?? document.createElement("script");
    script.type = "module";
    script.async = true;
    script.src = CHATKIT_SCRIPT_URL;
    script.dataset.chatkit = "true";

    script.addEventListener("load", () => {
      if (window.ChatKit) {
        scriptState.status = "loaded";
        resolve(window.ChatKit);
      } else {
        reject(new Error("ChatKit script loaded without defining window.ChatKit."));
      }
    });

    script.addEventListener("error", () => {
      scriptState.status = "idle";
      reject(new Error("Failed to load ChatKit script."));
    });

    if (!existing) {
      document.head.appendChild(script);
    }
  });

  return scriptState.promise;
}

export default function ChatAgent() {
  const [token, setToken] = useState(null);
  const [ChatKitCtor, setChatKitCtor] = useState(null);

  useEffect(() => {
    const stored = localStorage.getItem("access_token");
    setToken(stored);
  }, []);

  useEffect(() => {
    let active = true;

    loadChatKit()
      .then((ctor) => {
        if (active) {
          setChatKitCtor(() => ctor);
        }
      })
      .catch((error) => {
        console.error("chatkit_load_failed", error);
      });

    return () => {
      active = false;
    };
  }, []);

  const agent = useMemo(() => {
    if (!ChatKitCtor || !token) {
      return null;
    }

    try {
      return new ChatKitCtor({
        baseUrl: "/api/agents/analytics",
        token: async () => token,
        passThrough: true,
      });
    } catch (error) {
      console.error("chatkit_init_failed", error);
      return null;
    }
  }, [ChatKitCtor, token]);

  if (!token || !agent) {
    return <div>Loading chat...</div>;
  }

  const ChatComponent = agent.Chat;

  return (
    <div
      style={{
        height: "600px",
        marginTop: "24px",
        border: "1px solid #ccc",
        borderRadius: "8px",
      }}
    >
      <ChatComponent />
    </div>
  );
}
