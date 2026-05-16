import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL   = import.meta.env.VITE_WS_URL   || "ws://localhost:8000/ws";
const REST_URL = import.meta.env.VITE_REST_URL  || "http://localhost:8000/snapshot";
const POLL_MS  = 5000;

export function useWebSocket() {
  const [data, setData]           = useState(null);
  const [connected, setConnected] = useState(false);
  const ws        = useRef(null);
  const reconnect = useRef(null);
  const poll      = useRef(null);
  const connectRef = useRef(null);

  // REST poll — runs always so the dashboard isn't blank while WS reconnects
  const startPoll = useCallback(() => {
    const tick = async () => {
      try {
        const res = await fetch(REST_URL);
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.warn("Snapshot poll failed", e);
      }
      poll.current = setTimeout(tick, POLL_MS);
    };
    tick();
  }, []);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => setConnected(true);
    ws.current.onclose = () => {
      setConnected(false);
      reconnect.current = setTimeout(() => connectRef.current?.(), 3000);
    };
    ws.current.onerror = () => ws.current.close();
    ws.current.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data));
      } catch (err) {
        console.warn("WebSocket message parse failed", err);
      }
    };
  }, []);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    startPoll();
    return () => {
      clearTimeout(reconnect.current);
      clearTimeout(poll.current);
      ws.current?.close();
    };
  }, [connect, startPoll]);

  return { data, connected };
}
