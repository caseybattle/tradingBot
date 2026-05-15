import { useEffect, useState } from "react";

const REST_BASE = import.meta.env.VITE_REST_URL?.replace("/snapshot", "") || "http://localhost:8000";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};
const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 4 };

function Metric({ label, value, target, higherBetter = true, fmt = (v) => v }) {
  const passes = target !== undefined
    ? (higherBetter ? value >= target : value <= target)
    : null;
  const color = passes === null ? "#aaa" : passes ? "#00ff88" : "#ff4455";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={LBL}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "monospace" }}>
        {fmt(value)}
      </div>
      {target !== undefined && (
        <div style={{ fontSize: 10, color: "#333", marginTop: 2 }}>
          {higherBetter ? `min ${fmt(target)}` : `max ${fmt(target)}`}
        </div>
      )}
    </div>
  );
}

export function BacktestPanel() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen]       = useState(false);

  const run = async () => {
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(`${REST_BASE}/backtest`);
      setData(await res.json());
    } catch (e) {
      setData({ status: "error", detail: String(e) });
    }
    setLoading(false);
  };

  const reset = async () => {
    await fetch(`${REST_BASE}/backtest/reset`, { method: "POST" });
    setData(null);
    setLoading(false);
    run();
  };

  return (
    <div style={{ ...CARD, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: open && data ? 16 : 0 }}>
        <div>
          <div style={{ fontSize: 11, color: "#555", letterSpacing: 2 }}>BACKTEST RESULTS</div>
          {data?.note && <div style={{ fontSize: 10, color: "#333", marginTop: 2 }}>{data.note}</div>}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {data && (
            <button onClick={reset} style={{
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
              color: "#666", fontSize: 11, padding: "4px 12px", borderRadius: 6, cursor: "pointer",
            }}>
              RE-RUN
            </button>
          )}
          <button onClick={data ? () => setOpen(!open) : run} style={{
            background: data?.gate === "PASS" ? "rgba(0,255,136,0.1)" : data?.gate === "FAIL" ? "rgba(255,68,85,0.1)" : "rgba(0,255,136,0.08)",
            border: `1px solid ${data?.gate === "PASS" ? "rgba(0,255,136,0.3)" : data?.gate === "FAIL" ? "rgba(255,68,85,0.3)" : "rgba(0,255,136,0.2)"}`,
            color: data?.gate === "PASS" ? "#00ff88" : data?.gate === "FAIL" ? "#ff4455" : "#00ff88",
            fontSize: 11, fontWeight: 700, letterSpacing: 1,
            padding: "4px 16px", borderRadius: 6, cursor: "pointer",
          }}>
            {loading ? "RUNNING..." : data ? (open ? "HIDE" : data.gate) : "RUN BACKTEST"}
          </button>
        </div>
      </div>

      {open && loading && (
        <div style={{ textAlign: "center", color: "#555", fontSize: 13, padding: "24px 0" }}>
          Fetching 8 days of 15m candles + running strategy...
        </div>
      )}

      {open && data && !loading && data.status === "error" && (
        <div style={{ color: "#ff4455", fontSize: 12 }}>Error: {data.detail}</div>
      )}

      {open && data && !loading && data.status === "ok" && (
        <>
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            background: data.gate === "PASS" ? "rgba(0,255,136,0.06)" : "rgba(255,68,85,0.06)",
            border: `1px solid ${data.gate === "PASS" ? "rgba(0,255,136,0.15)" : "rgba(255,68,85,0.15)"}`,
            borderRadius: 8, padding: "10px 16px", marginBottom: 16,
          }}>
            <div style={{
              fontSize: 18, fontWeight: 800,
              color: data.gate === "PASS" ? "#00ff88" : "#ff4455",
            }}>
              {data.gate === "PASS" ? "✓ GO" : "✗ NO-GO"}
            </div>
            <div style={{ fontSize: 12, color: "#666" }}>
              {data.gate === "PASS"
                ? "Strategy cleared gate. Safe to paper trade."
                : "Strategy failed gate. Sharpe < 0.8 or drawdown > 35%."}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            <Metric label="TOTAL RETURN" value={data.total_return_pct}
              fmt={(v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`} />
            <Metric label="SHARPE RATIO" value={data.sharpe_ratio} target={0.8}
              higherBetter={true} fmt={(v) => v.toFixed(2)} />
            <Metric label="MAX DRAWDOWN" value={data.max_drawdown_pct} target={35}
              higherBetter={false} fmt={(v) => `${v.toFixed(1)}%`} />
            <Metric label="WIN RATE" value={data.win_rate}
              fmt={(v) => `${v.toFixed(1)}%`} />
            <Metric label="TOTAL TRADES" value={data.total_trades}
              fmt={(v) => v} />
            <Metric label="PROFIT FACTOR" value={data.profit_factor} target={1.0}
              higherBetter={true} fmt={(v) => v === Infinity ? "∞" : v.toFixed(2)} />
          </div>
          <div style={{ fontSize: 10, color: "#2a2a2a", marginTop: 12, textAlign: "center" }}>
            Note: Kraken public API ~8 days of 15m data. Limited sample — paper trading is primary validation.
          </div>
        </>
      )}
    </div>
  );
}
