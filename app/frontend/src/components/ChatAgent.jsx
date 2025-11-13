import { useEffect, useState } from "react";
import { ChatKit } from "@openai/chatkit";

export default function ChatAgent() {
  const [token, setToken] = useState(null);

  useEffect(() => {
    const t = localStorage.getItem("access_token");
    setToken(t);
  }, []);

  if (!token) {
    return <div>Loading chat...</div>;
  }

  const agent = new ChatKit({
    baseUrl: "/api/agents/analytics",
    token: async () => token,
    passThrough: true
  });

  return (
    <div style={{
      height: "600px",
      border: "1px solid #ccc",
      borderRadius: "8px",
      marginTop: "2rem"
    }}>
      <agent.Chat />
    </div>
  );
}
