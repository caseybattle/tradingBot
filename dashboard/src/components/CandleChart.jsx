import { useEffect, useRef, useState, useCallback } from "react";
import { createChart, ColorType, CandlestickSeries } from "lightweight-charts";

const REST_URL = import.meta.env.VITE_REST_URL?.replace("/snapshot", "") || "http://localhost:8000";

const TIMEFRAMES = [
  { label: "1m",  value: 1 },
  { label: "5m",  value: 5 },
  { label: "15m", value: 15 },
  { label: "1h",  value: 60 },
];

const BTN = (active) => ({
  background: active ? "rgba(0,255,136,0.12)" : "rgba(255,255,255,0.03)",
  border: `1px solid ${active ? "rgba(0,255,136,0.3)" : "rgba(255,255,255,0.08)"}`,
  color: active ? "#00ff88" : "#555",
  fontSize: 11, padding: "3px 10px", borderRadius: 5, cursor: "pointer",
});

export function CandleChart() {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);
  const seriesRef    = useRef(null);
  const [tf, setTf]  = useState(15);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#666",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: {
        borderColor: "rgba(255,255,255,0.08)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "rgba(255,255,255,0.2)", width: 1, style: 3 },
        horzLine: { color: "rgba(255,255,255,0.2)", width: 1, style: 3 },
      },
      width: containerRef.current.clientWidth,
      height: 300,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor:         "#00ff88",
      downColor:       "#ff4455",
      borderUpColor:   "#00ff88",
      borderDownColor: "#ff4455",
      wickUpColor:     "#00ff88",
      wickDownColor:   "#ff4455",
    });

    chartRef.current  = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  const loadCandles = useCallback(async (interval) => {
    if (!seriesRef.current) return;
    setLoading(true);
    try {
      const res = await fetch(`${REST_URL}/candles?count=150&interval=${interval}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.length > 0) {
        const sorted = [...data].sort((a, b) => a.time - b.time);
        seriesRef.current.setData(sorted);
        chartRef.current?.timeScale().fitContent();
        setLastUpdate(new Date().toLocaleTimeString());
      }
    } catch (e) {
      console.warn("Candle load failed", e);
    }
    setLoading(false);
  }, []);

  // Reload when timeframe changes
  useEffect(() => {
    const firstLoad = setTimeout(() => loadCandles(tf), 0);
    const refreshMs = tf <= 5 ? 15000 : tf === 15 ? 30000 : 60000;
    const id = setInterval(() => loadCandles(tf), refreshMs);
    return () => {
      clearTimeout(firstLoad);
      clearInterval(id);
    };
  }, [tf, loadCandles]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div style={{ fontSize: 11, color: "#555", letterSpacing: 2 }}>
          PI_XBTUSD - {TIMEFRAMES.find(t => t.value === tf)?.label} CANDLES
          {loading && <span style={{ marginLeft: 8, color: "#333" }}>...</span>}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {TIMEFRAMES.map(t => (
            <button key={t.value} onClick={() => setTf(t.value)} style={BTN(tf === t.value)}>
              {t.label}
            </button>
          ))}
          {lastUpdate && <span style={{ fontSize: 10, color: "#333", marginLeft: 4 }}>updated {lastUpdate}</span>}
        </div>
      </div>
      <div ref={containerRef} />
    </div>
  );
}
