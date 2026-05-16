import { useEffect, useState } from "react";

const REST_URL = import.meta.env.VITE_REST_URL?.replace("/snapshot", "") || "http://localhost:8000";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
};
const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };

function StatBox({ label, value, color }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={LBL}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "monospace", color: color || "#e0e0e0" }}>
        {value}
      </div>
    </div>
  );
}

export function TradeJournal() {
  const [trades, setTrades] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetch(`${REST_URL}/trades?limit=200`)
      .then(r => r.json())
      .then(setTrades)
      .catch(() => {});
  }, []);

  const wins    = trades.filter(t => t.pnl > 0);
  const losses  = trades.filter(t => t.pnl <= 0);
  const winRate = trades.length > 0 ? (wins.length / trades.length * 100).toFixed(1) : null;
  const avgWin  = wins.length > 0  ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.pnl, 0) / losses.length) : 0;
  const pf      = avgLoss > 0 ? (avgWin * wins.length) / (avgLoss * losses.length) : null;
  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
  const expectancy = trades.length > 0
    ? ((wins.length / trades.length) * avgWin - (losses.length / trades.length) * avgLoss).toFixed(2)
    : null;

  return (
    <div style={{ ...CARD, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: open ? 16 : 0 }}>
        <div style={{ fontSize: 11, color: "#555", letterSpacing: 2 }}>
          TRADE JOURNAL
          <span style={{ color: "#333", marginLeft: 8 }}>{trades.length} trades</span>
        </div>
        <button onClick={() => setOpen(o => !o)} style={{
          background: "transparent", border: "1px solid rgba(255,255,255,0.08)",
          color: "#555", fontSize: 11, padding: "3px 12px", borderRadius: 5, cursor: "pointer",
        }}>
          {open ? "HIDE" : "SHOW"}
        </button>
      </div>

      {open && trades.length === 0 && (
        <div style={{ color: "#333", fontSize: 13, textAlign: "center", padding: "20px 0" }}>
          No closed trades yet. First trade will appear here after it closes.
        </div>
      )}

      {open && trades.length > 0 && (
        <>
          {/* Summary stats */}
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12,
            background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: "14px 16px", marginBottom: 16,
          }}>
            <StatBox label="WIN RATE" value={winRate ? `${winRate}%` : "—"}
              color={winRate ? (parseFloat(winRate) >= 50 ? "#00ff88" : "#ffa500") : "#555"} />
            <StatBox label="PROFIT FACTOR" value={pf ? pf.toFixed(2) : "—"}
              color={pf ? (pf >= 1.5 ? "#00ff88" : pf >= 1.0 ? "#ffa500" : "#ff4455") : "#555"} />
            <StatBox label="EXPECTANCY" value={expectancy ? `$${expectancy}` : "—"}
              color={expectancy ? (parseFloat(expectancy) > 0 ? "#00ff88" : "#ff4455") : "#555"} />
            <StatBox label="AVG WIN" value={avgWin > 0 ? `+$${avgWin.toFixed(2)}` : "—"} color="#00ff88" />
            <StatBox label="AVG LOSS" value={avgLoss > 0 ? `-$${avgLoss.toFixed(2)}` : "—"} color="#ff4455" />
          </div>

          {/* Trade table */}
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ color: "#444", fontSize: 10, letterSpacing: 1 }}>
                  <th style={{ textAlign: "left",  padding: "4px 8px" }}>#</th>
                  <th style={{ textAlign: "left",  padding: "4px 8px" }}>SIDE</th>
                  <th style={{ textAlign: "right", padding: "4px 8px" }}>ENTRY</th>
                  <th style={{ textAlign: "right", padding: "4px 8px" }}>EXIT</th>
                  <th style={{ textAlign: "right", padding: "4px 8px" }}>SIZE</th>
                  <th style={{ textAlign: "right", padding: "4px 8px" }}>P&L</th>
                  <th style={{ textAlign: "right", padding: "4px 8px" }}>DATE</th>
                </tr>
              </thead>
              <tbody>
                {[...trades].reverse().map((t, i) => {
                  const won = t.pnl > 0;
                  const date = new Date(t.closed_at * 1000);
                  return (
                    <tr key={i} style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                      <td style={{ padding: "6px 8px", color: "#333" }}>{trades.length - i}</td>
                      <td style={{ padding: "6px 8px" }}>
                        <span style={{
                          color: t.side === "long" ? "#00ff88" : "#ff4455",
                          fontWeight: 700, fontSize: 11,
                        }}>
                          {t.side === "long" ? "▲ LONG" : "▼ SHORT"}
                        </span>
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "monospace", color: "#aaa" }}>
                        ${t.entry?.toLocaleString()}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "monospace", color: "#aaa" }}>
                        ${t.exit?.toLocaleString()}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: "#555" }}>
                        {t.size} BTC
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "monospace", fontWeight: 700,
                        color: won ? "#00ff88" : "#ff4455" }}>
                        {won ? "+" : ""}${t.pnl?.toFixed(2)}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: "#444", fontSize: 10 }}>
                        {date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}>
                  <td colSpan={5} style={{ padding: "8px", color: "#555", fontSize: 11 }}>TOTAL</td>
                  <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", fontWeight: 800,
                    color: totalPnl >= 0 ? "#00ff88" : "#ff4455", fontSize: 14 }}>
                    {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
