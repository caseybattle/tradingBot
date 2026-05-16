import { useEffect, useState } from "react";
import { getJson, postJson } from "../api";

const CARD = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: "12px 16px",
  marginBottom: 12,
};

const LBL = { fontSize: 10, color: "#555", letterSpacing: 2, marginBottom: 4 };

export function MarketSelector() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function loadMarkets() {
      try {
        const next = await getJson("/markets");
        if (!cancelled) setData(next);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    loadMarkets();
    return () => {
      cancelled = true;
    };
  }, []);

  const change = async (event) => {
    const symbol = event.target.value;
    setLoading(true);
    setError(null);
    try {
      const next = await postJson("/markets/active", { symbol });
      setData(next);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14 }}>
        <div>
          <div style={LBL}>MARKET</div>
          <select
            aria-label="MARKET"
            value={data?.active_symbol ?? "PI_XBTUSD"}
            onChange={change}
            disabled={loading || !data}
            style={{
              background: "#071625",
              color: "#e0e0e0",
              border: "1px solid rgba(255,255,255,0.14)",
              borderRadius: 6,
              padding: "8px 10px",
              fontSize: 13,
              minWidth: 210,
            }}
          >
            {(data?.markets ?? []).map((market) => (
              <option key={market.symbol} value={market.symbol}>
                {market.symbol} · {market.label}
              </option>
            ))}
          </select>
        </div>
        <div style={{ fontSize: 11, color: "#555", textAlign: "right" }}>
          Kraken crypto first<br />
          {loading ? "Switching..." : data?.scope ?? "BTC first"}
        </div>
      </div>
      {error && <div style={{ color: "#ff4455", fontSize: 12, marginTop: 8 }}>{error}</div>}
    </div>
  );
}
