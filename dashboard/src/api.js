const rawBase =
  import.meta.env.VITE_API_BASE ||
  import.meta.env.VITE_REST_URL?.replace(/\/snapshot\/?$/, "") ||
  "http://localhost:8000";

export const REST_BASE = rawBase.replace(/\/$/, "");

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
