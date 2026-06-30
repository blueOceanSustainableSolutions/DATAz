// ── Geo / motion math utilities ───────────────────────────────────────────────

export function formatDistance(m) {
  if (m == null || isNaN(m)) return "—";
  if (m >= 1000) return `${(m / 1000).toFixed(2)} km`;
  return `${Math.round(m)} m`;
}
