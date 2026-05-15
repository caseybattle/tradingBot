export function TradeLog({ trades = [] }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 8,
      padding: "12px 16px",
      maxHeight: 260,
      overflowY: "auto",
    }}>
      <div style={{ fontSize: 11, color: "#888", letterSpacing: 2, marginBottom: 10 }}>
        TRADE LOG
      </div>
      {trades.length === 0 && (
        <div style={{ color: "#555", fontSize: 13 }}>No trades yet</div>
      )}
      {[...trades].reverse().map((t, i) => {
        const isWin = t.pnl > 0;
        const ts = new Date(t.time * 1000).toLocaleTimeString();
        return (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "6px 0",
              borderBottom: "1px solid rgba(255,255,255,0.05)",
              fontSize: 13,
              fontFamily: "monospace",
            }}
          >
            <span style={{
              color: t.side === "long" ? "#00ff88" : "#ff4455",
              fontWeight: 600,
              width: 44,
            }}>
              {t.side.toUpperCase()}
            </span>
            <span style={{ color: "#aaa", flex: 1, textAlign: "center" }}>
              {t.entry?.toFixed(0)} → {t.exit?.toFixed(0)}
            </span>
            <span style={{ color: isWin ? "#00ff88" : "#ff4455", width: 80, textAlign: "right" }}>
              {isWin ? "+" : ""}{t.pnl?.toFixed(2)}
            </span>
            <span style={{ color: "#555", width: 72, textAlign: "right", fontSize: 11 }}>
              {ts}
            </span>
          </div>
        );
      })}
    </div>
  );
}
