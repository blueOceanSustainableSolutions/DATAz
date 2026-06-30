// Single-deployment detection endpoints from the source app
// (`/hydrotwin/:id/detections/*`) have no counterpart in the open backend, which
// only serves the site-level `/api/ai_detections/*` routes. The shared detection
// components import these names for their single-deployment code path; in this
// site-only build that path is never taken (every card receives `siteContext`),
// so these are guarded stubs that fail loudly if ever reached.

const NOT_SUPPORTED =
  "Single-deployment detection endpoints are not available in the open build; " +
  "use the site-level /api/ai_detections routes via src/api/detections.js.";

export function fetchRecentDetections() {
  return Promise.reject(new Error(NOT_SUPPORTED));
}

export function fetchDetectionsBinInspection() {
  return Promise.reject(new Error(NOT_SUPPORTED));
}

export function fetchDetectionsBins() {
  return Promise.reject(new Error(NOT_SUPPORTED));
}
