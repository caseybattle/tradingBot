import { useEffect, useState } from "react";
import { getJson } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};

const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };

function Field({ label, value, color = "#d8d8d8" }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#444", letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 14, color, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

export function StrategyCard({ signal, rsi, supertrendDir, funding, position }) {
  const [strategy, setStrategy] = useState(null);
  const [safety, setSafety] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [strategyData, safetyData] = await Promise.all([
          getJson("/strategy"),
          getJson("/safety"),
        ]);
        if (!cancelled) {
          setStrategy(strategyData);
          setSafety(safetyData);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const mode = safety?.mode ?? "loading";
  const modeColor = mode === "paper" ? "#00ff88" : mode === "live" ? "#ffa500" : "#ff4455";
  const params = strategy?.parameters ?? {};
  const risk = strategy?.risk ?? {};
  const source = strategy?.backtest_source ?? {};

  return (
    <div style={{ ...CARD, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", marginBottom: 18 }}>
        <div>
          <div style={LBL}>STRATEGY CARD</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: "#fff" }}>
            {strategy?.name ?? "Loading strategy"}
          </div>
          <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
            {strategy?.market?.exchange ?? "Kraken Futures"} · {strategy?.market?.symbol ?? "PI_XBTUSD"} · {strategy?.market?.candle_interval_minutes ?? 15}m
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 10, color: "#444", letterSpacing: 2 }}>MODE</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: modeColor }}>{mode.toUpperCase()}</div>
          <div style={{ fontSize: 10, color: "#555", marginTop: 3 }}>
            bot {safety?.bot_running ? "running" : "stopped"}
          </div>
        </div>
      </div>

      {error && <div style={{ color: "#ff4455", fontSize: 12, marginBottom: 12 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 12, marginBottom: 16 }}>
        <Field label="SIGNAL" value={signal ?? "HOLD"} color={signal === "BUY" ? "#00ff88" : signal === "SELL" ? "#ff4455" : "#aaa"} />
        <Field label="RSI GUARD" value={`${params.rsi_lower ?? 35} / ${params.rsi_upper ?? 65}`} />
        <Field label="SUPERTREND" value={`${params.supertrend_period ?? 10}, ${params.supertrend_multiplier ?? 3}`} />
        <Field label="ADX MIN" value={params.adx_min ?? 25} />
        <Field label="FUNDING CAP" value={`±${((params.funding_rate_threshold ?? 0.0005) * 100).toFixed(3)}%`} />
        <Field label="CONFIRM" value={params.confirmation_candle ? "required" : "off"} />
        <Field label="SESSION" value={params.session_filter ? "0-4am ET blocked" : "off"} />
        <Field label="POSITION" value={position ? `${position.side} ${position.size}` : "flat"} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
        <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 14 }}>
          <div style={LBL}>RISK SETTINGS</div>
          <div style={{ fontSize: 12, color: "#888", lineHeight: 1.7 }}>
            Risk {risk.risk_per_trade_pct ?? 2}% per trade · stop {risk.stop_distance_pct ?? 1.5}% · target {risk.target_multiple ?? 2}R · max ${risk.max_position_usd?.toLocaleString?.() ?? 5000}
          </div>
        </div>
        <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 14 }}>
          <div style={LBL}>BACKTEST SOURCE</div>
          <div style={{ fontSize: 12, color: "#888", lineHeight: 1.7 }}>
            {source.data ?? "Binance.us BTCUSD 15m"} · fees {source.fees ?? "0.05% commission per fill"} · slippage {source.slippage ?? "not modeled"}
          </div>
        </div>
        <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 14 }}>
          <div style={LBL}>LIVE SAFETY</div>
          <div style={{ fontSize: 12, color: safety?.allow_live_trading ? "#ffa500" : "#00ff88", lineHeight: 1.7 }}>
            {safety?.allow_live_trading ? "Live gate enabled" : "Live gate disabled"} · Kraken demo {safety?.kraken_demo ? "on" : "off"}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 10, color: "#333", marginTop: 14 }}>
        Current inputs: RSI {Number(rsi ?? 0).toFixed(1)} · SuperTrend {supertrendDir ?? 0} · Funding {((funding ?? 0) * 100).toFixed(4)}%
      </div>
    </div>
  );
}
