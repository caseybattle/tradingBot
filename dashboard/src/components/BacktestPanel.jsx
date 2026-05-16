import { useState } from "react";
import { REST_BASE } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};
const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 4 };

function Metric({ label, value, target, higherBetter = true, fmt = (v) => v }) {
  const safeValue = Number.isFinite(value) ? value : 0;
  const passes = target !== undefined
    ? (higherBetter ? safeValue >= target : safeValue <= target)
    : null;
  const color = passes === null ? "#aaa" : passes ? "#00ff88" : "#ff4455";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={LBL}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "monospace" }}>
        {Number.isFinite(value) ? fmt(value) : "—"}
      </div>
      {target !== undefined && (
        <div style={{ fontSize: 10, color: "#333", marginTop: 2 }}>
          {higherBetter ? `min ${fmt(target)}` : `max ${fmt(target)}`}
        </div>
      )}
    </div>
  );
}

const TOGGLE_BTN = (active) => ({
  background: active ? "rgba(0,255,136,0.12)" : "rgba(255,255,255,0.03)",
  border: `1px solid ${active ? "rgba(0,255,136,0.3)" : "rgba(255,255,255,0.08)"}`,
  color: active ? "#00ff88" : "#555",
  fontSize: 10, padding: "2px 8px", borderRadius: 4, cursor: "pointer", letterSpacing: 1,
});

export function BacktestPanel() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen]       = useState(false);
  const [years, setYears]     = useState(1);
  const [adx, setAdx]         = useState(true);
  const [session, setSession] = useState(true);
  const [confirm, setConfirm] = useState(true);

  const run = async (y = years, a = adx, s = session, c = confirm) => {
    setLoading(true);
    setOpen(true);
    try {
      await fetch(`${REST_BASE}/backtest/reset`, { method: "POST" });
      const params = new URLSearchParams({
        years: y,
        adx_min: a ? 25 : 0,
        session_filter: s,
        confirmation: c,
      });
      const res = await fetch(`${REST_BASE}/backtest?${params}`);
      setData(await res.json());
    } catch (e) {
      setData({ status: "error", detail: String(e) });
    }
    setLoading(false);
  };

  return (
    <div style={{ ...CARD, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: open && data ? 16 : 0 }}>
        <div>
          <div style={{ fontSize: 11, color: "#555", letterSpacing: 2 }}>BACKTEST RESULTS</div>
          {data?.filters && <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>filters: {data.filters}</div>}
          {data?.note && <div style={{ fontSize: 10, color: "#333", marginTop: 2 }}>{data.note}</div>}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {/* filter toggles */}
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <button onClick={() => setAdx(v => !v)} style={TOGGLE_BTN(adx)}>ADX</button>
            <button onClick={() => setSession(v => !v)} style={TOGGLE_BTN(session)}>SESSION</button>
            <button onClick={() => setConfirm(v => !v)} style={TOGGLE_BTN(confirm)}>CONFIRM</button>
          </div>
          <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.08)" }} />
          {[1, 2, 3, 5].map(y => (
            <button key={y} onClick={() => { setYears(y); if (data) run(y); }} style={{
              background: years === y ? "rgba(0,255,136,0.12)" : "rgba(255,255,255,0.03)",
              border: `1px solid ${years === y ? "rgba(0,255,136,0.3)" : "rgba(255,255,255,0.08)"}`,
              color: years === y ? "#00ff88" : "#555",
              fontSize: 11, padding: "3px 10px", borderRadius: 5, cursor: "pointer",
            }}>{y}Y</button>
          ))}
          <button onClick={() => run(years)} style={{
            background: data?.gate === "PASS" ? "rgba(0,255,136,0.1)" : data?.gate === "FAIL" ? "rgba(255,68,85,0.1)" : "rgba(0,255,136,0.08)",
            border: `1px solid ${data?.gate === "PASS" ? "rgba(0,255,136,0.3)" : data?.gate === "FAIL" ? "rgba(255,68,85,0.3)" : "rgba(0,255,136,0.2)"}`,
            color: data?.gate === "PASS" ? "#00ff88" : data?.gate === "FAIL" ? "#ff4455" : "#00ff88",
            fontSize: 11, fontWeight: 700, letterSpacing: 1,
            padding: "4px 16px", borderRadius: 6, cursor: "pointer",
          }}>
            {loading ? `FETCHING ${years}Y...` : data && !loading ? (open ? "HIDE" : data.gate ?? "RUN") : "RUN BACKTEST"}
          </button>
        </div>
      </div>

      {open && loading && (
        <div style={{ textAlign: "center", color: "#555", fontSize: 13, padding: "24px 0" }}>
          Fetching {years} year{years === 1 ? "" : "s"} of 15m candles and running strategy...
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

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 16 }}>
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
            Source: {data.data_source} · Fees: {data.fees} · Slippage: {data.slippage} · Gate: {data.gate_rules}
          </div>
        </>
      )}
    </div>
  );
}
