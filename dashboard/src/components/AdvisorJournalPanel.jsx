import { useEffect, useState } from "react";
import { getJson } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
  marginBottom: 12,
};

const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };

function money(value) {
  if (value === null || value === undefined) return "-";
  return `$${Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

function timeAgo(ts) {
  if (!ts) return "never";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export function AdvisorJournalPanel({ snapshot }) {
  const [journal, setJournal] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const data = await getJson("/advisor/journal?limit=6");
      setJournal(data);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function guardedLoad() {
      try {
        const data = await getJson("/advisor/journal?limit=6");
        if (!cancelled) {
          setJournal(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    guardedLoad();
    const id = setInterval(guardedLoad, 20000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [snapshot?.current_signal, snapshot?.active_symbol]);

  const summary = journal?.summary ?? {};
  const signals = journal?.signals ?? [];

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
        <div>
          <div style={LBL}>ADVISOR SIGNAL JOURNAL</div>
          <div style={{ fontSize: 22, fontWeight: 850, color: signals.length ? "#00ff88" : "#777" }}>
            {summary.actionable ?? 0} ACTIONABLE
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 4 }}>
            Auto-saves advisor plans. No exchange orders.
          </div>
        </div>
        <button
          onClick={load}
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.08)",
            color: "#888",
            borderRadius: 6,
            padding: "6px 10px",
            fontSize: 11,
            cursor: "pointer",
          }}
        >
          REFRESH
        </button>
      </div>

      {error && <div style={{ color: "#ff4455", fontSize: 12, marginBottom: 12 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12, marginBottom: 14 }}>
        <Stat label="TOTAL" value={summary.total ?? 0} />
        <Stat label="LONG" value={summary.long ?? 0} color="#00ff88" />
        <Stat label="SHORT" value={summary.short ?? 0} color="#ff4455" />
        <Stat label="OPEN" value={summary.open_outcomes ?? 0} />
      </div>

      {signals.length === 0 ? (
        <div style={{ fontSize: 12, color: "#777", lineHeight: 1.6 }}>
          No actionable advisor signals captured yet. First BUY, SELL, or managed-position plan will appear here automatically.
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {signals.map((item) => (
            <div key={item.id} style={{
              display: "grid",
              gridTemplateColumns: "1fr auto",
              gap: 12,
              background: "rgba(255,255,255,0.02)",
              borderRadius: 8,
              padding: 12,
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 850, color: item.side === "long" ? "#00ff88" : "#ff4455" }}>
                  {item.symbol} - {item.side?.toUpperCase() ?? item.signal} - {item.confidence}
                </div>
                <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                  Entry {money(item.entry_reference)} - Stop {money(item.stop)} - Target {money(item.target)}
                </div>
                <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
                  {item.thesis}
                </div>
              </div>
              <div style={{ textAlign: "right", fontSize: 11, color: "#555" }}>
                <div>{timeAgo(item.last_seen_at)}</div>
                <div style={{ marginTop: 4 }}>{item.seen_count}x seen</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color = "#d8d8d8" }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 10, color: "#444", letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, color, fontWeight: 850 }}>{value}</div>
    </div>
  );
}
