const isBrowser = typeof window !== "undefined";
const isLocalHost = isBrowser && ["localhost", "127.0.0.1"].includes(window.location.hostname);
const localApiHost = isBrowser ? window.location.hostname : "localhost";
const isProductionHost = isBrowser && !isLocalHost;
const localBase =
  import.meta.env.VITE_API_BASE ||
  import.meta.env.VITE_REST_URL?.replace(/\/snapshot\/?$/, "") ||
  `http://${localApiHost}:8000`;

const rawBase = isProductionHost ? "/api" : localBase;

export const REST_BASE = rawBase.replace(/\/$/, "");
export const SNAPSHOT_URL =
  isProductionHost ? `${REST_BASE}/snapshot` : import.meta.env.VITE_REST_URL || `${REST_BASE}/snapshot`;
const envWsUrl = import.meta.env.DEV ? import.meta.env.VITE_WS_URL : undefined;
export const WS_URL = isProductionHost ? "" : envWsUrl || `ws://${localApiHost}:8000/ws`;

export async function getJson(path) {
  const res = await fetch(`${REST_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function postJson(path, body) {
  const res = await fetch(`${REST_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
