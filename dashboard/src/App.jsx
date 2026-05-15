import { useWebSocket } from "./hooks/useWebSocket";
import { PnLCounter } from "./components/PnLCounter";
import { ParticleCanvas } from "./components/ParticleCanvas";
import { TradeLog } from "./components/TradeLog";
import { PnLChart } from "./components/PnLChart";

export default function App() {
  const { data, connected } = useWebSocket();

  const pnl = data?.pnl_total ?? 0;
  const pnlPct = data?.pnl_pct ?? 0;
  const capital = data?.capital ?? 0;
  const position = data?.position;
  const trades = data?.trades ?? [];
  const equity = data?.equity_history ?? [];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060e1a",
      color: "#e0e0e0",
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      position: "relative",
      overflow: "hidden",
    }}>
      <ParticleCanvas pnl={pnl} />

      <div style={{ position: "relative", zIndex: 1, padding: "32px 40px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 40 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: 1 }}>BTC TRADER</div>
            <div style={{ fontSize: 12, color: "#555", marginTop: 2 }}>PI_XBTUSD · Kraken Futures</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: connected ? "#00ff88" : "#ff4455" }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: connected ? "#00ff88" : "#ff4455",
              boxShadow: connected ? "0 0 8px #00ff88" : "none",
            }} />
            {connected ? "LIVE" : "DISCONNECTED"}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20, marginBottom: 32 }}>
          <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "24px 20px" }}>
            <PnLCounter value={pnl} />
            <div style={{ textAlign: "center", marginTop: 6, fontSize: 14, color: pnl >= 0 ? "#00ff88" : "#ff4455" }}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
            </div>
          </div>

          <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "24px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "#888", letterSpacing: 2, marginBottom: 8 }}>BALANCE</div>
            <div style={{ fontSize: 36, fontWeight: 700, fontFamily: "monospace" }}>
              ${capital.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
          </div>

          <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "24px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "#888", letterSpacing: 2, marginBottom: 8 }}>POSITION</div>
            {position ? (
              <>
                <div style={{ fontSize: 22, fontWeight: 700, color: position.side === "long" ? "#00ff88" : "#ff4455" }}>
                  {position.side.toUpperCase()}
                </div>
                <div style={{ fontSize: 13, color: "#aaa", marginTop: 4 }}>
                  {position.size} BTC @ ${position.entry?.toFixed(0)}
                </div>
                <div style={{ fontSize: 11, color: "#666", marginTop: 6 }}>
                  SL ${position.stop?.toFixed(0)} · TP ${position.target?.toFixed(0)}
                </div>
              </>
            ) : (
              <div style={{ fontSize: 18, color: "#555" }}>FLAT</div>
            )}
          </div>
        </div>

        <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "20px 20px 12px", marginBottom: 20 }}>
          <PnLChart equityHistory={equity} />
        </div>

        <TradeLog trades={trades} />
      </div>
    </div>
  );
}
