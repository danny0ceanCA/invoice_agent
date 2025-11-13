import ChatAgent from "../components/ChatAgent.jsx";

export default function Analytics() {
  return (
    <div className="analytics-page" style={{ padding: "1rem 0" }}>
      <h2 style={{ fontSize: "1.5rem", fontWeight: 600, marginBottom: "1rem" }}>
        Analytics
      </h2>

      <p style={{ color: "#4b5563", maxWidth: "700px", marginBottom: "1.5rem" }}>
        Dive into spending trends, vendor utilization, and budget insights.
        Ask questions using the AI Analytics Assistant to generate reports instantly.
      </p>

      <ChatAgent />
    </div>
  );
}
