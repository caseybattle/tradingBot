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

function metric(value, suffix = "") {
  if (value === null || value === undefined) return "-";
  return `${Number(value).toFixed(2)}${suffix}`;
}

export function ProofGatePanel() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getJson("/strategy/validation");
        if (!cancelled) setReport(data);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const pass = report?.gate === "PASS";
  const full = report?.full_sample ?? {};
  const inSample = report?.in_sample ?? {};
  const out = report?.out_of_sample ?? {};

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
        <div>
          <div style={LBL}>PROOF GATE</div>
          <div style={{ fontSize: 22, fontWeight: 850, color: pass ? "#00ff88" : "#ff4455" }}>
            {report ? `STRICT ${report.gate}` : "LOADING"}
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 4 }}>
            Candidate strategy only until strict validation passes.
          </div>
        </div>
        <div style={{ textAlign: "right", fontSize: 11, color: "#555" }}>
          {report?.symbol ?? "PI_XBTUSD"} · {report?.candles?.toLocaleString?.() ?? 0} candles
        </div>
      </div>

      {error && <div style={{ color: "#ff4455", fontSize: 12, marginBottom: 12 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
        <Window title="FULL" data={full} />
        <Window title="IN SAMPLE" data={inSample} />
        <Window title="OUT SAMPLE" data={out} />
      </div>

      <div style={{ marginTop: 14, fontSize: 12, color: "#888", lineHeight: 1.6 }}>
        {report?.reason ?? "Requires split validation, slippage, fees, drawdown, Sharpe, profit factor, and trade count checks."}
      </div>
    </div>
  );
}

function Window({ title, data }) {
  const pass = data?.gate === "PASS";
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 14 }}>
      <div style={{ ...LBL, marginBottom: 8 }}>{title}</div>
      <div style={{ color: pass ? "#00ff88" : "#ff4455", fontWeight: 850, fontSize: 16 }}>{data?.gate ?? "-"}</div>
      <div style={{ fontSize: 12, color: "#aaa", lineHeight: 1.7, marginTop: 8 }}>
        Sharpe {metric(data?.sharpe_ratio)}<br />
        Drawdown {metric(data?.max_drawdown_pct, "%")}<br />
        Profit factor {metric(data?.profit_factor)}<br />
        Trades {data?.total_trades ?? 0}
      </div>
    </div>
  );
}
