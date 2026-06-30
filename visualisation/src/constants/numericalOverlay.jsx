import { NUMERICAL_VIZ_ENABLED } from "@/config";

/**
 * Numerical Visualizer (NetCDF map-overlay) — shared constants & pure helpers.
 *
 * The visualizer is a self-contained tab that plays time-animated raster overlays
 * (WaveWatch III / RAINDROP …) produced by the netcdf-preprocessor and served by the
 * backend's map-overlays module (manifest + SAS-signed frame URLs).
 *
 * In the source app this tab is gated to a single site by slug. This open build IS
 * that single site, so the gate is just the build-time `NUMERICAL_VIZ_ENABLED` flag.
 */

// Synthetic tab appended by the orchestrator. `custom` tells SiteTabBar to render the
// lazy viewer panel instead of a ChartGrid; `order` keeps it last.
export const NUMERICAL_VIZ_TAB = {
  id: "numericalViz",
  label: "Numerical Visualizer",
  order: 100,
  custom: true,
};

/** True when this build should expose the Numerical Visualizer tab. The source app
 *  gated by site slug; here it's a single-site build, so it's an env-backed flag.
 *  Keeps the `(siteId)` signature the orchestrator calls with. */
export function isNumericalVizSite() {
  return NUMERICAL_VIZ_ENABLED;
}

// Token-less MapLibre raster basemaps — same family SiteMap uses, so the open build
// needs no map-provider key. Each is a complete style object (single raster source).
function rasterStyle(tiles, attribution) {
  return {
    version: 8,
    sources: { basemap: { type: "raster", tiles, tileSize: 256, attribution } },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

export const OVERLAY_BASEMAPS = {
  light: rasterStyle(
    ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    "© OpenStreetMap contributors",
  ),
  dark: rasterStyle(
    [
      "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    ],
    "© OpenStreetMap contributors, © CARTO",
  ),
  satellite: rasterStyle(
    [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    "© Esri, Maxar, Earthstar Geographics",
  ),
};

export const OVERLAY_BASEMAP_OPTIONS = [
  { key: "light", label: "Light" },
  { key: "dark", label: "Dark" },
  { key: "satellite", label: "Satellite" },
];

// CSS-gradient stops mirroring the matplotlib colormaps the preprocessor bakes into the
// frames, so the legend matches the rendered pixels. (Sampled at 10–14 stops.)
export const OVERLAY_COLORMAP_STOPS = {
  viridis: ["#440154", "#482878", "#3e4a89", "#31688e", "#26828e",
            "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
  turbo: ["#30123b", "#4145ab", "#4675ed", "#39a2fc", "#1bcfd4", "#24eca6", "#61fc6c",
          "#a4fc3b", "#d1e834", "#f3c63a", "#fe9b2d", "#f36315", "#cb2a04", "#7a0403"],
  magma: ["#000004", "#1c1044", "#4f127b", "#812581", "#b5367a",
          "#e55064", "#fb8761", "#fec287", "#fcfdbf"],
  plasma: ["#0d0887", "#4b03a1", "#7d03a8", "#a82296", "#cb4679",
           "#e56b5d", "#f89441", "#fdc328", "#f0f921"],
  // Cyclic — wave / peak direction (0° and 360° share the same colour).
  twilight: ["#e2d9e2", "#b3c6ce", "#7ba1c2", "#6276ba", "#5e43a5", "#4e186f",
             "#2f1436", "#581647", "#8e2c50", "#b25652", "#c6896c", "#d4bcac", "#e2d9e2"],
};

export function overlayGradientCss(name) {
  const stops = OVERLAY_COLORMAP_STOPS[name] || OVERLAY_COLORMAP_STOPS.viridis;
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

// ── Result grouping & labels ───────────────────────────────────────────────────
// A NetCDF yields several results (one per variable) that share a `dataset`, so the
// dataset dropdown lists files and the variable dropdown lists that file's variables.

/** Group key: the originating dataset (a WW3 grid file yields hs / pdir / rtp). */
export function overlayDatasetKey(r) {
  return r.dataset || r.source_file || r.id;
}

/** "dataz_ww3_grd1_2026_06" → "WW3 grd1 (2026-06)"; "dataz_raindrop_2025_06" → "RAINDROP (2025-06)". */
export function overlayDatasetLabel(key) {
  const parts = String(key).replace(/^dataz_/, "").replace(/\.nc$/, "").split("_");
  const sim = (parts.shift() || "").toUpperCase();
  let date = "";
  if (parts.length >= 2 && /^\d{4}$/.test(parts[parts.length - 2]) && /^\d{2}$/.test(parts[parts.length - 1])) {
    date = `${parts[parts.length - 2]}-${parts[parts.length - 1]}`;
    parts.splice(parts.length - 2, 2);
  }
  const middle = parts.join(" ");
  return `${sim}${middle ? " " + middle : ""}${date ? ` (${date})` : ""}`;
}

/** "HS · significant wave height" (falls back to the result id). */
export function overlayVariableLabel(r) {
  const name = (r.variable?.name || r.id).toUpperCase();
  return r.variable?.long_name ? `${name} · ${r.variable.long_name}` : name;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => String(n).padStart(2, "0");

/** "2026-06-03T13:00:00Z" → "Jun 03, 2026 · 13:00 UTC". */
export function formatOverlayTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${MONTHS[d.getUTCMonth()]} ${pad(d.getUTCDate())}, ${d.getUTCFullYear()} · ` +
         `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}

/** Human duration for a decimation step: "10 min" / "1 hr" / "6 hr" / "1 day". */
export function humanizeDuration(sec) {
  if (sec < 3600) return `${Math.round(sec / 60)} min`;
  if (sec < 86400) return `${Math.round(sec / 3600)} hr`;
  const days = Math.round(sec / 86400);
  return `${days} day${days > 1 ? "s" : ""}`;
}

/**
 * Decimation presets derived from the dataset's real frame interval: every frame, then
 * ~1h / ~6h / ~1day of model time. Honest labels for 10-min RAINDROP and hourly WW3.
 * Returns `[{ value, label }]` where `value` is the frame stride.
 */
export function buildStepOptions(intervalSeconds) {
  const iv = intervalSeconds && intervalSeconds > 0 ? intervalSeconds : 600;
  const seen = new Set();
  const opts = [];
  for (const target of [iv, 3600, 6 * 3600, 24 * 3600]) {
    const value = Math.max(1, Math.round(target / iv));
    if (seen.has(value)) continue;
    seen.add(value);
    opts.push({ value, label: humanizeDuration(value * iv) });
  }
  return opts;
}

export const OVERLAY_FPS_OPTIONS = [2, 4, 8, 15, 30];
