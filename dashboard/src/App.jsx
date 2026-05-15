import { useWebSocket } from "./hooks/useWebSocket";
import { PnLCounter } from "./components/PnLCounter";
import { ParticleCanvas } from "./components/ParticleCanvas";
import { TradeLog } from "./components/TradeLog";
import { PnLChart } from "./components/PnLChart";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};
const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };

function StatCard({ label, children, style = {} }) {
  return (
    <div style={{ ...CARD, ...style }}>
      <div style={LBL}>{label}</div>
      {children}
    </div>
  );
}

function RsiGauge({ rsi }) {
  const color = rsi < 30 || rsi > 70 ? "#ff4455" : rsi > 60 ? "#ffa500" : "#00ff88";
  const zone = rsi < 30 ? "OVERSOLD" : rsi > 70 ? "OVERBOUGHT" : "NEUTRAL";
  return (
    <StatCard label="RSI (14)">
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 32, fontWeight: 800, color }}>{rsi.toFixed(1)}</span>
        <span style={{ fontSize: 11, color: "#555" }}>{zone}</span>
      </div>
      <div style={{ position: "relative", height: 5, background: "rgba(255,255,255,0.07)", borderRadius: 3 }}>
        <div style={{
          position: "absolute", left: "30%", right: "30%",
          top: 0, bottom: 0, background: "rgba(255,255,255,0.05)",
        }} />
        <div style={{
          position: "absolute",
          left: `${Math.min(Math.max(rsi, 2), 98)}%`,
          top: -4, width: 12, height: 12,
          background: color, borderRadius: "50%",
          transform: "translateX(-50%)",
          boxShadow: `0 0 6px ${color}`,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#333", marginTop: 5 }}>
        <span>0</span><span>30</span><span>50</span><span>70</span><span>100</span>
      </div>
    </StatCard>
  );
}

export default function App() {
  const { data, connected } = useWebSocket();

  const pnl          = data?.pnl_total ?? 0;
  const pnlPct       = data?.pnl_pct ?? 0;
  const capital      = data?.capital ?? 0;
  const position     = data?.position ?? null;
  const trades       = data?.trades ?? [];
  const equity       = data?.equity_history ?? [];
  const lastPrice    = data?.last_price ?? 0;
  const rsi          = data?.rsi ?? 0;
  const stDir        = data?.supertrend_dir ?? 0;
  const funding      = data?.funding_rate ?? 0;
  const wins         = data?.wins ?? 0;
  const losses       = data?.losses ?? 0;
  const winRate      = data?.win_rate ?? 0;
  const bestTrade    = data?.best_trade ?? 0;
  const worstTrade   = data?.worst_trade ?? 0;
  const totalTrades  = wins + losses;

  const pnlColor     = pnl >= 0 ? "#00ff88" : "#ff4455";
  const stColor      = stDir === 1 ? "#00ff88" : stDir === -1 ? "#ff4455" : "#555";
  const fundingColor = funding > 0 ? "#ff4455" : funding < 0 ? "#00ff88" : "#888";
  const fundingPct   = (funding * 100).toFixed(4);
  const unrealized   = position?.unrealized_pnl ?? 0;

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

      <div style={{ position: "relative", zIndex: 1, padding: "22px 32px", maxWidth: 1400, margin: "0 auto" }}>

        {/* HEADER */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "#333", letterSpacing: 3 }}>BATTLE LABS</div>
            <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: 1, marginTop: 2 }}>BTC TRADER</div>
            <div style={{ fontSize: 11, color: "#444", marginTop: 2 }}>PI_XBTUSD · Kraken Futures · 15m</div>
          </div>
          <div style={{ textAlign: "right" }}>
            {lastPrice > 0 && (
              <div style={{ fontSize: 38, fontWeight: 800, fontFamily: "monospace", color: "#fff", letterSpacing: -1 }}>
                ${lastPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            )}
            {lastPrice === 0 && (
              <div style={{ fontSize: 22, color: "#333", fontFamily: "monospace" }}>-- Connecting --</div>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end", marginTop: 4 }}>
              <div style={{
                width: 7, height: 7, borderRadius: "50%",
                background: connected ? "#00ff88" : "#ff4455",
                boxShadow: connected ? "0 0 8px #00ff88" : "none",
              }} />
              <span style={{ fontSize: 11, color: connected ? "#00ff88" : "#ff4455", letterSpacing: 2 }}>
                {connected ? "LIVE" : "DISCONNECTED"}
              </span>
            </div>
          </div>
        </div>

        {/* ROW 1: Core stats */}
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>

          <StatCard label="TOTAL P&L">
            <PnLCounter value={pnl} />
            <div style={{ fontSize: 13, color: pnlColor, marginTop: 4 }}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
            </div>
          </StatCard>

          <StatCard label="BALANCE" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 700, fontFamily: "monospace" }}>
              ${capital.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </StatCard>

          <StatCard label="WIN RATE" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 30, fontWeight: 800, color: totalTrades === 0 ? "#555" : winRate >= 50 ? "#00ff88" : "#ff4455" }}>
              {totalTrades === 0 ? "—" : `${winRate.toFixed(1)}%`}
            </div>
            <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
              {wins}W · {losses}L · {totalTrades} trades
            </div>
          </StatCard>

          <StatCard label="BEST / WORST" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#00ff88" }}>
              {bestTrade !== 0 ? `+$${bestTrade.toFixed(2)}` : "—"}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#ff4455", marginTop: 6 }}>
              {worstTrade !== 0 ? `$${worstTrade.toFixed(2)}` : "—"}
            </div>
          </StatCard>
        </div>

        {/* ROW 2: Signals */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr 1fr", gap: 12, marginBottom: 12 }}>

          <StatCard label="SUPERTREND (10, 3.0)" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: stColor, marginBottom: 4 }}>
              {stDir === 1 ? "▲ BULL" : stDir === -1 ? "▼ BEAR" : "— WAIT"}
            </div>
            <div style={{ fontSize: 11, color: "#444" }}>
              {stDir === 1 ? "Bullish trend active" : stDir === -1 ? "Bearish trend active" : "Awaiting flip signal"}
            </div>
          </StatCard>

          <RsiGauge rsi={rsi} />

          <StatCard label="FUNDING RATE" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: fundingColor, fontFamily: "monospace" }}>
              {funding > 0 ? "+" : ""}{fundingPct}%
            </div>
            <div style={{ fontSize: 11, color: "#555", marginTop: 6 }}>
              {funding > 0 ? "Longs paying shorts" : funding < 0 ? "Shorts paying longs" : "Neutral"}
            </div>
            <div style={{ fontSize: 10, color: "#333", marginTop: 2 }}>threshold ±0.05%</div>
          </StatCard>
        </div>

        {/* ROW 3: Position */}
        {position ? (
          <div style={{
            ...CARD,
            marginBottom: 12,
            borderColor: position.side === "long" ? "rgba(0,255,136,0.25)" : "rgba(255,68,85,0.25)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <div style={LBL}>OPEN POSITION</div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    fontSize: 20, fontWeight: 800,
                    color: position.side === "long" ? "#00ff88" : "#ff4455",
                    background: position.side === "long" ? "rgba(0,255,136,0.1)" : "rgba(255,68,85,0.1)",
                    padding: "3px 14px", borderRadius: 6,
                  }}>
                    {position.side.toUpperCase()}
                  </div>
                  <div style={{ fontSize: 16, fontFamily: "monospace", fontWeight: 700 }}>
                    {position.size} BTC
                  </div>
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={LBL}>UNREALIZED P&L</div>
                <div style={{
                  fontSize: 28, fontWeight: 800, fontFamily: "monospace",
                  color: unrealized >= 0 ? "#00ff88" : "#ff4455",
                }}>
                  {unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}
                </div>
              </div>
            </div>
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
              gap: 12, paddingTop: 14,
              borderTop: "1px solid rgba(255,255,255,0.06)",
            }}>
              <div>
                <div style={{ ...LBL, marginBottom: 3 }}>ENTRY</div>
                <div style={{ fontSize: 18, fontFamily: "monospace", fontWeight: 700 }}>
                  ${position.entry?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </div>
              </div>
              <div>
                <div style={{ ...LBL, color: "#ff4455", marginBottom: 3 }}>STOP LOSS</div>
                <div style={{ fontSize: 18, fontFamily: "monospace", fontWeight: 700, color: "#ff4455" }}>
                  ${position.stop?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </div>
              </div>
              <div>
                <div style={{ ...LBL, color: "#00ff88", marginBottom: 3 }}>TAKE PROFIT</div>
                <div style={{ fontSize: 18, fontFamily: "monospace", fontWeight: 700, color: "#00ff88" }}>
                  ${position.target?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ ...CARD, marginBottom: 12, textAlign: "center", padding: "14px 20px" }}>
            <div style={LBL}>POSITION</div>
            <div style={{ fontSize: 16, color: "#333", fontWeight: 600 }}>FLAT — Waiting for SuperTrend flip</div>
          </div>
        )}

        {/* ROW 4: Equity curve */}
        <div style={{ ...CARD, marginBottom: 12, padding: "16px 20px 8px" }}>
          <PnLChart equityHistory={equity} />
        </div>

        {/* ROW 5: Trade log */}
        <TradeLog trades={trades} />
      </div>
    </div>
  );
}
