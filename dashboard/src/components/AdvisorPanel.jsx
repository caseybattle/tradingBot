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

export function AdvisorPanel({ snapshot }) {
  const [advisor, setAdvisor] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getJson("/advisor");
        if (!cancelled) setAdvisor(data);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [snapshot?.current_signal, snapshot?.last_price]);

  const rec = advisor?.recommendation ?? {};
  const actionColor = rec.action === "consider_entry" ? "#00ff88" : rec.action === "manage_existing_position" ? "#ffa500" : "#aaa";

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <div style={LBL}>ADVISOR</div>
          <div style={{ fontSize: 22, fontWeight: 850, color: actionColor }}>
            {(rec.action ?? "loading").replaceAll("_", " ").toUpperCase()}
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 4 }}>
            {advisor?.symbol ?? snapshot?.active_symbol ?? "PI_XBTUSD"} · confidence {advisor?.confidence ?? "loading"} · no automatic orders
          </div>
        </div>
        <div style={{ textAlign: "right", fontSize: 11, color: advisor?.places_orders ? "#ff4455" : "#00ff88", letterSpacing: 1 }}>
          {advisor?.places_orders ? "ORDERING ENABLED" : "READ ONLY"}
        </div>
      </div>

      {error && <div style={{ color: "#ff4455", fontSize: 12, marginBottom: 12 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <Field label="SIDE" value={rec.side?.toUpperCase?.() ?? "WAIT"} color={rec.side === "long" ? "#00ff88" : rec.side === "short" ? "#ff4455" : "#aaa"} />
        <Field label="ENTRY REF" value={money(rec.entry_reference ?? rec.entry)} />
        <Field label="SIZE" value={rec.size ? `${rec.size} BTC` : "-"} />
        <Field label="STOP" value={money(rec.stop)} color="#ff4455" />
        <Field label="TARGET" value={money(rec.target)} color="#00ff88" />
        <Field label="RISK" value={money(rec.risk_usd)} />
      </div>

      <div style={{ marginTop: 14, fontSize: 12, color: "#888", lineHeight: 1.6 }}>
        {rec.invalidation ?? rec.do_nothing_reason ?? rec.reason ?? "Waiting for live signal state."}
      </div>
    </div>
  );
}

function Field({ label, value, color = "#d8d8d8" }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 10, color: "#444", letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 15, color, fontWeight: 800 }}>{value}</div>
    </div>
  );
}
