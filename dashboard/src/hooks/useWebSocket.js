import { useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

export function useWebSocket() {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const ws = useRef(null);
  const reconnect = useRef(null);

  const connect = () => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => setConnected(true);
    ws.current.onclose = () => {
      setConnected(false);
      reconnect.current = setTimeout(connect, 3000);
    };
    ws.current.onerror = () => ws.current.close();
    ws.current.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data));
      } catch {}
    };
  };

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnect.current);
      ws.current?.close();
    };
  }, []);

  return { data, connected };
}
