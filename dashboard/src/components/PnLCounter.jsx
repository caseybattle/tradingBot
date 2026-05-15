import { useEffect, useRef } from "react";

function easeOut(t) {
  return 1 - Math.pow(1 - t, 3);
}

export function PnLCounter({ value = 0, duration = 800 }) {
  const ref = useRef(null);
  const prev = useRef(0);
  const frame = useRef(null);

  useEffect(() => {
    const start = prev.current;
    const end = value;
    const startTime = performance.now();

    const tick = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const current = start + (end - start) * easeOut(progress);

      if (ref.current) {
        const formatted = current.toLocaleString("en-US", {
          style: "currency",
          currency: "USD",
          minimumFractionDigits: 2,
        });
        ref.current.textContent = formatted;
        ref.current.style.color = end >= 0 ? "#00ff88" : "#ff4455";
      }

      if (progress < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        prev.current = end;
      }
    };

    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [value, duration]);

  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 13, color: "#888", letterSpacing: 2, marginBottom: 6 }}>
        TOTAL P&amp;L
      </div>
      <div
        ref={ref}
        style={{
          fontSize: 52,
          fontWeight: 700,
          fontFamily: "'Courier New', monospace",
          textShadow: "0 0 20px currentColor",
          transition: "color 0.3s",
        }}
      />
    </div>
  );
}
