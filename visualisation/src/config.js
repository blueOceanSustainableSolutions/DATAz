// Public runtime configuration.

const env = import.meta.env;

// Production backend API base (includes the `/api` suffix).
export const API_BASE = (
  env.VITE_API_BASE_URL ||
  "https://hydrotwin-prod-backend.agreeableriver-a8000f03.northeurope.azurecontainerapps.io/api"
).replace(/\/+$/, "");

// Explicit site id. When empty, the app uses the first (only) site this account
// can access, discovered from `GET /api/sites` at runtime.
export const SITE_ID = env.VITE_SITE_ID || null;

// Title shown in the header and browser tab.
export const PAGE_TITLE = env.VITE_PAGE_TITLE || "DATAz";

// Read-only backend API key sent as `X-API-Key`.
export const API_KEY =
  env.VITE_API_KEY || "ht_org_DM5Tl2bjsH_ZI6PBhdhO0h5l9Lz4C4RXc4KkaDNyliM";

// Numerical Visualizer (NetCDF map-overlay player). In the source app this tab is
// gated to a single site by slug; this open build IS that single site, so it's on
// by default. Set VITE_ENABLE_NUMERICAL_VIZ="false" to hide it (e.g. against a
// backend without the map-overlays module).
export const NUMERICAL_VIZ_ENABLED =
  String(env.VITE_ENABLE_NUMERICAL_VIZ ?? "true").toLowerCase() !== "false";
