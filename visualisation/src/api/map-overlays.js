import { API, getJson } from "./http";

/**
 * Map-overlay transport (Numerical Visualizer).
 *
 * Talks to the backend's map-overlays module:
 *   GET /api/map-overlays                 → MapOverlaySummaryDTO[]  (one per variable)
 *   GET /api/map-overlays/:id/manifest    → manifest + frame_base_url + sas_token
 *
 * Auth is the open build's read-only `X-API-Key` (via `getJson`), not a bearer
 * token. Frames are NOT proxied: the manifest carries a Blob base URL and a
 * short-lived read SAS token, so the browser fetches each PNG straight from
 * storage as `${frame_base_url}${frame.url}?${sas_token}` (see overlayFrameUrl).
 */

/** List available overlays (light summaries). Returns `MapOverlaySummaryDTO[]`. */
export function fetchMapOverlays() {
  return getJson(`${API}/map-overlays`);
}

/** Full manifest for one overlay, augmented with `frame_base_url` + `sas_token`. */
export function fetchMapOverlayManifest(id) {
  if (!id) throw new Error("overlay id is required");
  return getJson(`${API}/map-overlays/${encodeURIComponent(id)}/manifest`);
}

/**
 * Resolve a manifest frame's RELATIVE url against the Blob base + SAS token.
 * `frame_base_url` already ends with `/`; the token is appended as a query string.
 */
export function overlayFrameUrl(manifest, relativeUrl) {
  if (!manifest?.frame_base_url || !relativeUrl) return "";
  const sep = manifest.sas_token ? `?${manifest.sas_token}` : "";
  return `${manifest.frame_base_url}${relativeUrl}${sep}`;
}
