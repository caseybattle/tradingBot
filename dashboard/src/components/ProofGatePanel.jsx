import { useCallback, useEffect, useState } from "react";
import { getJson } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
  marginBottom: 12,
};

const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };
const YEARS = [1, 2, 3, 5];

const BTN = (active) => ({
  background: active ? "rgba(0,255,136,0.12)" : "rgba(255,255,255,0.03)",
  border: `1px solid ${active ? "rgba(0,255,136,0.3)" : "rgba(255,255,255,0.08)"}`,
  color: active ? "#00ff88" : "#555",
  fontSize: 11,
  padding: "4px 10px",
  borderRadius: 5,
  cursor: "pointer",
});

function metric(value, suffix = "") {
  if (value === null || value === undefined) return "-";
  return `${Number(value).toFixed(2)}${suffix}`;
}

export function ProofGatePanel() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [years, setYears] = useState(5);

  const load = useCallback(async (nextYears, cancelled = () => false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getJson(`/strategy/validation?years=${nextYears}`);
      if (!cancelled()) {
        setReport(data);
      }
    } catch (e) {
      if (!cancelled()) {
        setReport(null);
        setError(String(e));
      }
    } finally {
      if (!cancelled()) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    let isCancelled = false;
    const timer = window.setTimeout(() => {
      load(5, () => isCancelled);
    }, 0);
    return () => {
      isCancelled = true;
      window.clearTimeout(timer);
    };
  }, [load]);

  const run = async (nextYears = years) => {
    setYears(nextYears);
    await load(nextYears);
  };

  const pass = report?.gate === "PASS";
  const full = report?.full_sample ?? {};
  const inSample = report?.in_sample ?? {};
  const out = report?.out_of_sample ?? {};
  const status = report
    ? `STRICT ${report.years ?? years}Y ${report.gate}`
    : loading
      ? `RUNNING ${years}Y`
      : "CHECK FAILED";

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
        <div>
          <div style={LBL}>PROOF GATE</div>
          <div style={{ fontSize: 22, fontWeight: 850, color: pass ? "#00ff88" : "#ff4455" }}>
            {status}
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 4 }}>
            Candidate strategy only until strict validation passes.
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", justifyContent: "flex-end", flexWrap: "wrap" }}>
          {YEARS.map((option) => (
            <button key={option} onClick={() => run(option)} disabled={loading} style={BTN(years === option)}>
              {option}Y
            </button>
          ))}
          <button
            onClick={() => run(years)}
            disabled={loading}
            style={{
              background: "rgba(0,255,136,0.08)",
              border: "1px solid rgba(0,255,136,0.22)",
              color: "#00ff88",
              borderRadius: 6,
              padding: "5px 12px",
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: 1,
              cursor: "pointer",
            }}
          >
            {loading ? "RUNNING..." : error ? "RETRY" : "REFRESH"}
          </button>
        </div>
      </div>

      <div style={{ textAlign: "right", fontSize: 11, color: "#555", marginTop: -10, marginBottom: 12 }}>
        {report?.symbol ?? "PI_XBTUSD"} · {report?.candles?.toLocaleString?.() ?? "-"} candles
      </div>

      {error && (
        <div style={{
          color: "#ff4455",
          fontSize: 12,
          marginBottom: 12,
          background: "rgba(255,68,85,0.06)",
          border: "1px solid rgba(255,68,85,0.15)",
          borderRadius: 8,
          padding: "10px 12px",
        }}>
          Proof request failed: {error}. No live trading state changed.
        </div>
      )}

      {loading && !report && (
        <div style={{
          color: "#777",
          fontSize: 12,
          marginBottom: 12,
          background: "rgba(255,255,255,0.02)",
          borderRadius: 8,
          padding: "10px 12px",
        }}>
          Fetching {years} year{years === 1 ? "" : "s"} of 15m candles, fees, slippage, split windows, and walk-forward checks.
        </div>
      )}

      {report && (
        <div style={{ fontSize: 11, color: "#555", marginBottom: 12 }}>
          Source: {report.data_source} · Fees {report.assumptions?.fee_pct_per_fill}% · Slippage {report.assumptions?.slippage_pct_per_fill}%
        </div>
      )}

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
