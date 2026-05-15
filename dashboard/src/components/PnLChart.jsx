import { useEffect, useRef } from "react";
import { createChart, ColorType, AreaSeries } from "lightweight-charts";

export function PnLChart({ equityHistory = [] }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#888",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
      width: containerRef.current.clientWidth,
      height: 180,
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#00ff88",
      topColor: "rgba(0,255,136,0.25)",
      bottomColor: "rgba(0,255,136,0)",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || equityHistory.length === 0) return;
    const points = equityHistory
      .map(([ts, val]) => ({ time: Math.floor(ts), value: val }))
      .sort((a, b) => a.time - b.time);

    // deduplicate by time
    const seen = new Set();
    const deduped = points.filter(p => {
      if (seen.has(p.time)) return false;
      seen.add(p.time);
      return true;
    });

    seriesRef.current.setData(deduped);
    chartRef.current?.timeScale().fitContent();
  }, [equityHistory]);

  return (
    <div>
      <div style={{ fontSize: 11, color: "#888", letterSpacing: 2, marginBottom: 8 }}>
        EQUITY CURVE
      </div>
      <div ref={containerRef} />
    </div>
  );
}
