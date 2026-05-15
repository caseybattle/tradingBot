import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CandlestickSeries } from "lightweight-charts";

const REST_URL = import.meta.env.VITE_REST_URL?.replace("/snapshot", "") || "http://localhost:8000";

export function CandleChart({ position }) {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);
  const seriesRef    = useRef(null);
  const [lastUpdate, setLastUpdate] = useState(null);

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
      height: 280,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor:          "#00ff88",
      downColor:        "#ff4455",
      borderUpColor:    "#00ff88",
      borderDownColor:  "#ff4455",
      wickUpColor:      "#00ff88",
      wickDownColor:    "#ff4455",
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

  // Draw entry/stop/target lines when position changes
  useEffect(() => {
    if (!chartRef.current) return;
    // lightweight-charts v5: price lines on the series
    if (!seriesRef.current) return;
    // Clear existing price lines by removing and re-adding (v5 has no clearPriceLines)
    // We'll recreate them via the series options approach
  }, [position]);

  // Fetch candles from REST
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(`${REST_URL}/candles?count=100`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && seriesRef.current && data.length > 0) {
          const sorted = [...data].sort((a, b) => a.time - b.time);
          seriesRef.current.setData(sorted);
          chartRef.current?.timeScale().fitContent();
          setLastUpdate(new Date().toLocaleTimeString());
        }
      } catch {}
    };
    load();
    const id = setInterval(load, 60000); // refresh every minute
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: "#555", letterSpacing: 2 }}>PI_XBTUSD — 15m CANDLES</div>
        {lastUpdate && (
          <div style={{ fontSize: 10, color: "#333" }}>updated {lastUpdate}</div>
        )}
      </div>
      <div ref={containerRef} />
    </div>
  );
}
