import { useState } from "react";
import { postJson } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};

const COMMANDS = [
  "show journal",
  "show leaderboard",
  "run backtest",
  "explain signal",
  "show risk",
  "start paper bot",
  "stop paper bot",
  "close paper position",
];

function summarizeData(data) {
  if (!data) return null;
  if (data.gate) {
    return `${data.gate} · ${data.total_return_pct?.toFixed?.(1)}% return · Sharpe ${data.sharpe_ratio?.toFixed?.(2)} · DD ${data.max_drawdown_pct?.toFixed?.(1)}%`;
  }
  if (Array.isArray(data.rows)) {
    const leader = data.rows[0];
    return leader
      ? `${data.trusted_count} trusted · leader ${leader.strategy_name} on ${leader.symbol} · gate ${leader.gate}`
      : "No leaderboard rows yet.";
  }
  if (Array.isArray(data.signals)) {
    return `${data.summary?.actionable ?? 0} actionable signals · ${data.summary?.open_outcomes ?? 0} open outcomes`;
  }
  if (data.signal) {
    return data.summary;
  }
  if (data.mode) {
    return `${data.mode} · bot ${data.bot_running ? "running" : "stopped"}`;
  }
  if (data.safety?.mode) {
    return `${data.safety.mode} · live gate ${data.safety.allow_live_trading ? "enabled" : "disabled"}`;
  }
  if (data.status) {
    return data.error ? `${data.error}: ${data.detail ?? ""}` : data.status;
  }
  return null;
}

export function ChatPanel() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([
    {
      role: "bot",
      text: "Ask for an approved action: show journal, show leaderboard, run backtest, explain signal, show risk, start paper bot, stop paper bot, or close paper position.",
    },
  ]);

  const send = async (text = message) => {
    const clean = text.trim();
    if (!clean || loading) return;
    setLoading(true);
    setMessage("");
    setHistory((items) => [...items, { role: "user", text: clean }]);
    try {
      const result = await postJson("/chat", { message: clean });
      const detail = summarizeData(result.data);
      setHistory((items) => [
        ...items,
        {
          role: "bot",
          text: detail ? `${result.answer} ${detail}` : result.answer,
          intent: result.intent,
        },
      ]);
    } catch (e) {
      setHistory((items) => [...items, { role: "bot", text: `Command failed: ${String(e)}` }]);
    }
    setLoading(false);
  };

  return (
    <div style={{ ...CARD, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: "#555", letterSpacing: 2 }}>CHAT CONTROL</div>
          <div style={{ fontSize: 11, color: "#444", marginTop: 3 }}>
            Deterministic commands only. No live trade placement from chat.
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "flex-end" }}>
          {COMMANDS.map((cmd) => (
            <button
              key={cmd}
              onClick={() => send(cmd)}
              disabled={loading}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "#888",
                fontSize: 10,
                borderRadius: 5,
                padding: "4px 8px",
                cursor: "pointer",
              }}
            >
              {cmd}
            </button>
          ))}
        </div>
      </div>

      <div style={{
        maxHeight: 220,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        marginBottom: 12,
      }}>
        {history.slice(-8).map((item, index) => (
          <div
            key={`${item.role}-${index}`}
            style={{
              alignSelf: item.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "86%",
              background: item.role === "user" ? "rgba(0,255,136,0.08)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${item.role === "user" ? "rgba(0,255,136,0.18)" : "rgba(255,255,255,0.06)"}`,
              color: item.role === "user" ? "#b8ffd8" : "#bbb",
              borderRadius: 8,
              padding: "8px 10px",
              fontSize: 12,
              lineHeight: 1.45,
            }}
          >
            {item.intent && (
              <div style={{ fontSize: 9, color: "#444", letterSpacing: 1, marginBottom: 3 }}>
                {item.intent}
              </div>
            )}
            {item.text}
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        style={{ display: "flex", gap: 8 }}
      >
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Ask: explain signal"
          style={{
            flex: 1,
            minWidth: 0,
            background: "rgba(0,0,0,0.24)",
            border: "1px solid rgba(255,255,255,0.08)",
            color: "#ddd",
            borderRadius: 7,
            padding: "10px 12px",
            outline: "none",
          }}
        />
        <button
          disabled={loading}
          style={{
            background: "rgba(0,255,136,0.1)",
            border: "1px solid rgba(0,255,136,0.25)",
            color: "#00ff88",
            borderRadius: 7,
            padding: "0 16px",
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          {loading ? "..." : "SEND"}
        </button>
      </form>
    </div>
  );
}
