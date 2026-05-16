import { useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { PnLCounter } from "./components/PnLCounter";
import { TradeLog } from "./components/TradeLog";
import { PnLChart } from "./components/PnLChart";
import { CandleChart } from "./components/CandleChart";
import { BacktestPanel } from "./components/BacktestPanel";

const REST_BASE = "http://localhost:8000";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};
const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };

function RsiGauge({ rsi }) {
  const color = rsi < 30 || rsi > 70 ? "#ff4455" : rsi > 60 ? "#ffa500" : "#00ff88";
  const zone  = rsi < 30 ? "OVERSOLD" : rsi > 70 ? "OVERBOUGHT" : "NEUTRAL";
  return (
    <div style={CARD}>
      <div style={LBL}>RSI (14)</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 32, fontWeight: 800, color }}>{rsi.toFixed(1)}</span>
        <span style={{ fontSize: 11, color: "#555" }}>{zone}</span>
      </div>
      <div style={{ position: "relative", height: 5, background: "rgba(255,255,255,0.07)", borderRadius: 3 }}>
        <div style={{ position: "absolute", left: "30%", right: "30%", top: 0, bottom: 0, background: "rgba(255,255,255,0.05)" }} />
        <div style={{
          position: "absolute", left: `${Math.min(Math.max(rsi, 2), 98)}%`,
          top: -4, width: 12, height: 12, background: color, borderRadius: "50%",
          transform: "translateX(-50%)", boxShadow: `0 0 6px ${color}`,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#333", marginTop: 5 }}>
        <span>0</span><span>30</span><span>50</span><span>70</span><span>100</span>
      </div>
    </div>
  );
}

function SignalBanner({ signal, position, lastPrice, onLong, onShort, onClose, loading }) {
  const hasSignal  = signal === "BUY" || signal === "SELL";
  const hasPos     = !!position;
  const unrealized = position?.unrealized_pnl ?? 0;

  if (hasPos) {
    const posColor = position.side === "long" ? "#00ff88" : "#ff4455";
    return (
      <div style={{
        borderRadius: 10, padding: "16px 20px", marginBottom: 14,
        background: position.side === "long" ? "rgba(0,255,136,0.06)" : "rgba(255,68,85,0.06)",
        border: `1px solid ${posColor}44`,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <div style={{ fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 4 }}>OPEN POSITION</div>
          <div style={{ display: "flex", gap: 16, alignItems: "baseline" }}>
            <span style={{ fontSize: 22, fontWeight: 800, color: posColor }}>{position.side.toUpperCase()}</span>
            <span style={{ fontFamily: "monospace", color: "#aaa" }}>{position.size} BTC @ ${position.entry?.toLocaleString()}</span>
          </div>
          <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>
            Stop <span style={{ color: "#ff4455" }}>${position.stop?.toLocaleString()}</span>
            &nbsp;·&nbsp;
            Target <span style={{ color: "#00ff88" }}>${position.target?.toLocaleString()}</span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 26, fontWeight: 800, fontFamily: "monospace", color: unrealized >= 0 ? "#00ff88" : "#ff4455" }}>
            {unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}
          </div>
          <div style={{ fontSize: 10, color: "#555", marginBottom: 8 }}>UNREALIZED P&L</div>
          <button onClick={onClose} disabled={loading} style={{
            background: "rgba(255,68,85,0.15)", border: "1px solid rgba(255,68,85,0.4)",
            color: "#ff4455", fontSize: 12, fontWeight: 700, letterSpacing: 1,
            padding: "6px 20px", borderRadius: 6, cursor: "pointer",
          }}>
            {loading ? "CLOSING..." : "CLOSE POSITION"}
          </button>
        </div>
      </div>
    );
  }

  if (hasSignal) {
    const isBuy  = signal === "BUY";
    const color  = isBuy ? "#00ff88" : "#ff4455";
    const bgCol  = isBuy ? "rgba(0,255,136,0.08)" : "rgba(255,68,85,0.08)";
    const border = isBuy ? "rgba(0,255,136,0.4)" : "rgba(255,68,85,0.4)";
    return (
      <div style={{
        borderRadius: 10, padding: "16px 20px", marginBottom: 14,
        background: bgCol, border: `2px solid ${border}`,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        animation: "pulse 1.5s infinite",
      }}>
        <div>
          <div style={{ fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 4 }}>SIGNAL DETECTED</div>
          <div style={{ fontSize: 24, fontWeight: 800, color }}>
            {isBuy ? "▲" : "▼"} {signal} SIGNAL
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 4 }}>
            SuperTrend flip confirmed · RSI filter passed · ${lastPrice?.toLocaleString()}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {isBuy && (
            <button onClick={onLong} disabled={loading} style={{
              background: "rgba(0,255,136,0.15)", border: "2px solid #00ff88",
              color: "#00ff88", fontSize: 14, fontWeight: 800, letterSpacing: 1,
              padding: "10px 28px", borderRadius: 8, cursor: "pointer",
            }}>
              {loading ? "PLACING..." : "▲ GO LONG"}
            </button>
          )}
          {!isBuy && (
            <button onClick={onShort} disabled={loading} style={{
              background: "rgba(255,68,85,0.15)", border: "2px solid #ff4455",
              color: "#ff4455", fontSize: 14, fontWeight: 800, letterSpacing: 1,
              padding: "10px 28px", borderRadius: 8, cursor: "pointer",
            }}>
              {loading ? "PLACING..." : "▼ GO SHORT"}
            </button>
          )}
          <button onClick={() => {}} style={{
            background: "transparent", border: "1px solid #333",
            color: "#555", fontSize: 12, padding: "10px 16px", borderRadius: 8, cursor: "pointer",
          }}>SKIP</button>
        </div>
      </div>
    );
  }

  // HOLD + FLAT
  return (
    <div style={{ ...CARD, marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <div>
        <div style={LBL}>SIGNAL STATUS</div>
        <div style={{ fontSize: 16, color: "#444", fontWeight: 600 }}>SCANNING — No signal yet</div>
        <div style={{ fontSize: 11, color: "#333", marginTop: 3 }}>Waiting for SuperTrend flip on 15m candle</div>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={onLong} disabled={loading} style={{
          background: "rgba(0,255,136,0.08)", border: "1px solid rgba(0,255,136,0.25)",
          color: "#00ff88", fontSize: 12, fontWeight: 700,
          padding: "8px 18px", borderRadius: 7, cursor: "pointer",
        }}>
          {loading ? "..." : "▲ LONG"}
        </button>
        <button onClick={onShort} disabled={loading} style={{
          background: "rgba(255,68,85,0.08)", border: "1px solid rgba(255,68,85,0.25)",
          color: "#ff4455", fontSize: 12, fontWeight: 700,
          padding: "8px 18px", borderRadius: 7, cursor: "pointer",
        }}>
          {loading ? "..." : "▼ SHORT"}
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const { data, connected } = useWebSocket();
  const [tradeLoading, setTradeLoading] = useState(false);

  const pnl       = data?.pnl_total ?? 0;
  const pnlPct    = data?.pnl_pct ?? 0;
  const capital   = data?.capital ?? 0;
  const position  = data?.position ?? null;
  const trades    = data?.trades ?? [];
  const equity    = data?.equity_history ?? [];
  const lastPrice = data?.last_price ?? 0;
  const rsi       = data?.rsi ?? 0;
  const stDir     = data?.supertrend_dir ?? 0;
  const funding   = data?.funding_rate ?? 0;
  const wins      = data?.wins ?? 0;
  const losses    = data?.losses ?? 0;
  const winRate   = data?.win_rate ?? 0;
  const bestTrade = data?.best_trade ?? 0;
  const worstTrade = data?.worst_trade ?? 0;
  const signal    = data?.current_signal ?? "HOLD";
  const totalTrades = wins + losses;

  const stColor   = stDir === 1 ? "#00ff88" : stDir === -1 ? "#ff4455" : "#555";
  const fundingColor = funding > 0 ? "#ff4455" : funding < 0 ? "#00ff88" : "#888";

  const placeOrder = async (side) => {
    setTradeLoading(true);
    try {
      await fetch(`${REST_BASE}/order?side=${side}`, { method: "POST" });
    } catch {}
    setTradeLoading(false);
  };

  const closePosition = async () => {
    setTradeLoading(true);
    try {
      await fetch(`${REST_BASE}/close`, { method: "POST" });
    } catch {}
    setTradeLoading(false);
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060e1a",
      color: "#e0e0e0",
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
    }}>
      <div style={{ padding: "20px 28px", maxWidth: 1400, margin: "0 auto" }}>

        {/* HEADER */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 11, color: "#333", letterSpacing: 3 }}>BATTLE LABS</div>
            <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: 1, marginTop: 2 }}>BTC TRADER</div>
            <div style={{ fontSize: 11, color: "#444", marginTop: 2 }}>PI_XBTUSD · Kraken Futures · 15m · {connected ? "Paper" : "Offline"}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 38, fontWeight: 800, fontFamily: "monospace", color: "#fff", letterSpacing: -1 }}>
              {lastPrice > 0 ? `$${lastPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "—"}
            </div>
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

        {/* SIGNAL BANNER — always first */}
        <SignalBanner
          signal={signal} position={position} lastPrice={lastPrice}
          onLong={() => placeOrder("long")}
          onShort={() => placeOrder("short")}
          onClose={closePosition}
          loading={tradeLoading}
        />

        {/* ROW 1: Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
          <div style={CARD}>
            <div style={LBL}>TOTAL P&L</div>
            <PnLCounter value={pnl} />
            <div style={{ fontSize: 13, color: pnl >= 0 ? "#00ff88" : "#ff4455", marginTop: 4 }}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
            </div>
          </div>
          <div style={{ ...CARD, textAlign: "center" }}>
            <div style={LBL}>BALANCE</div>
            <div style={{ fontSize: 26, fontWeight: 700, fontFamily: "monospace" }}>
              ${capital.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div style={{ ...CARD, textAlign: "center" }}>
            <div style={LBL}>WIN RATE</div>
            <div style={{ fontSize: 30, fontWeight: 800, color: totalTrades === 0 ? "#555" : winRate >= 50 ? "#00ff88" : "#ff4455" }}>
              {totalTrades === 0 ? "—" : `${winRate.toFixed(1)}%`}
            </div>
            <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>{wins}W · {losses}L · {totalTrades} trades</div>
          </div>
          <div style={{ ...CARD, textAlign: "center" }}>
            <div style={LBL}>BEST / WORST</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#00ff88" }}>{bestTrade !== 0 ? `+$${bestTrade.toFixed(2)}` : "—"}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#ff4455", marginTop: 6 }}>{worstTrade !== 0 ? `$${worstTrade.toFixed(2)}` : "—"}</div>
          </div>
        </div>

        {/* ROW 2: Signals */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr 1fr", gap: 12, marginBottom: 12 }}>
          <div style={{ ...CARD, textAlign: "center" }}>
            <div style={LBL}>SUPERTREND (10, 3.0)</div>
            <div style={{ fontSize: 26, fontWeight: 800, color: stColor, marginBottom: 4 }}>
              {stDir === 1 ? "▲ BULL" : stDir === -1 ? "▼ BEAR" : "— WAIT"}
            </div>
            <div style={{ fontSize: 11, color: "#444" }}>
              {stDir === 1 ? "Bullish trend active" : stDir === -1 ? "Bearish trend active" : "Awaiting flip signal"}
            </div>
          </div>
          <RsiGauge rsi={rsi} />
          <div style={{ ...CARD, textAlign: "center" }}>
            <div style={LBL}>FUNDING RATE</div>
            <div style={{ fontSize: 26, fontWeight: 800, color: fundingColor, fontFamily: "monospace" }}>
              {funding > 0 ? "+" : ""}{(funding * 100).toFixed(4)}%
            </div>
            <div style={{ fontSize: 11, color: "#555", marginTop: 6 }}>
              {funding > 0 ? "Longs paying shorts" : funding < 0 ? "Shorts paying longs" : "Neutral"}
            </div>
            <div style={{ fontSize: 10, color: "#333", marginTop: 2 }}>threshold ±0.05%</div>
          </div>
        </div>

        {/* ROW 3: Candle chart */}
        <div style={{ ...CARD, marginBottom: 12, padding: "16px 20px 8px" }}>
          <CandleChart position={position} />
        </div>

        {/* ROW 4: Equity curve (only when trades exist) */}
        {equity.length > 0 && (
          <div style={{ ...CARD, marginBottom: 12, padding: "16px 20px 8px" }}>
            <PnLChart equityHistory={equity} />
          </div>
        )}

        {/* ROW 5: Backtest */}
        <BacktestPanel />

        {/* ROW 6: Trade log */}
        <TradeLog trades={trades} />
      </div>
    </div>
  );
}
