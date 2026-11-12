// Points at your Laravel API. Set VITE_API_BASE_URL in an .env file
// for this project, e.g.:
//   VITE_API_BASE_URL=https://your-domain.example.com/api
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

async function getJson(path) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
    credentials: "include", // adjust if you're using Sanctum cookie auth
  });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed: ${res.status}`);
  }
  return res.json();
}

export function fetchSignals(limit = 100) {
  return getJson(`/signals?limit=${limit}`);
}

export function fetchPerformance() {
  return getJson("/signals/performance");
}
