import { useState } from "react";
import { getJson } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "18px 20px",
  marginBottom: 12,
};

const LBL = { fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 6 };

function fmt(value, digits = 2) {
  if (value === null || value === undefined) return "-";
  return Number(value).toFixed(digits);
}

export function ValidationLeaderboardPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const result = await getJson("/strategy/leaderboard?years=1");
      setData(result);
    } catch (e) {
      setError(String(e));
    }
    setLoading(false);
  }

  const rows = data?.rows ?? [];

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: rows.length ? 16 : 0 }}>
        <div>
          <div style={LBL}>VALIDATION LEADERBOARD</div>
          <div style={{ fontSize: 22, fontWeight: 850, color: data?.trusted_count ? "#00ff88" : "#ff4455" }}>
            {data ? `${data.trusted_count} TRUSTED` : "NOT RUN"}
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 4 }}>
            Ranks BTC and ETH strategy candidates with fees, slippage, split validation, and walk-forward gates.
          </div>
        </div>
        <button
          onClick={run}
          disabled={loading}
          style={{
            background: "rgba(0,255,136,0.08)",
            border: "1px solid rgba(0,255,136,0.22)",
            color: "#00ff88",
            borderRadius: 6,
            padding: "7px 12px",
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: 1,
            cursor: "pointer",
          }}
        >
          {loading ? "RUNNING..." : "RUN 1Y LEADERBOARD"}
        </button>
      </div>

      {error && <div style={{ color: "#ff4455", fontSize: 12, marginTop: 12 }}>{error}</div>}

      {!data && !loading && (
        <div style={{ fontSize: 12, color: "#777", lineHeight: 1.6, marginTop: 14 }}>
          Run this before trusting any strategy. It compares the current SuperTrend system against time-series momentum variants.
        </div>
      )}

      {rows.length > 0 && (
        <div style={{ display: "grid", gap: 8 }}>
          {rows.slice(0, 6).map((row) => (
            <div key={`${row.strategy_id}-${row.symbol}`} style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(86px, 1fr))",
              gap: 10,
              alignItems: "center",
              background: "rgba(255,255,255,0.02)",
              borderRadius: 8,
              padding: "10px 12px",
            }}>
              <Cell label="RANK" value={`#${row.rank}`} color="#aaa" />
              <div>
                <div style={{ fontSize: 13, fontWeight: 850, color: row.strict_pass ? "#00ff88" : "#ddd" }}>
                  {row.strategy_name} - {row.symbol}
                </div>
                <div style={{ fontSize: 10, color: "#555", marginTop: 3 }}>
                  {row.family} - {row.strict_pass ? "strict pass" : "locked"}
                </div>
              </div>
              <Cell label="GATE" value={row.gate} color={row.strict_pass ? "#00ff88" : "#ff4455"} />
              <Cell label="SCORE" value={fmt(row.score, 1)} />
              <Cell label="SHARPE" value={fmt(row.out_of_sample?.sharpe_ratio ?? row.full_sample?.sharpe_ratio)} />
              <Cell label="DD" value={`${fmt(row.full_sample?.max_drawdown_pct, 1)}%`} />
              <Cell label="PF" value={fmt(row.full_sample?.profit_factor)} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Cell({ label, value, color = "#d8d8d8" }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: "#444", letterSpacing: 1, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, color, fontWeight: 850 }}>{value}</div>
    </div>
  );
}
