/**
 * Hydrotwin type registry — the spine of the new site view.
 *
 * Single source of truth for per-type behavior on /site/[id]:
 *   - marker shape on the map (Phase 2)
 *   - rail-card variant (Phase 2)
 *   - which chart cards each hydrotwin participates in (Phase 1)
 *
 * Adding a future hydrotwin type ("HT-X") is one new entry here — not a
 * sweep through the codebase. Existing /scout/[id] code continues to use
 * `getScoutType` from constants/scoutConfig.js; the two helpers agree
 * on the prefix rule.
 */

const FULL_METOCEAN_SET = {
  waveHeight: true,
  wavePeriod: true,
  waveDirection: true,
  wind: true,
  barometric: true,
  dissolvedOxygen: true,
  current: true,
  tempHumidity: true,
};

const NO_METOCEAN_SET = {
  waveHeight: false,
  wavePeriod: false,
  waveDirection: false,
  wind: false,
  barometric: false,
  dissolvedOxygen: false,
  current: false,
  // tempHumidity is sourced from on-device sensors, so every type
  // contributes to it.
  tempHumidity: true,
};

const ACOUSTIC_SET = {
  aiDetections: true,
  broadbandSPL: true,
  octaveBands: true,
  spectrogram: true,
  anomaly: true,
};

export const HYDROTWIN_TYPE_REGISTRY = {
  "HT-S": {
    key: "HT-S",
    label: "Drifting",
    markerShape: "circle",
    hasLiveListen: false,
    hasSpotterPanel: true,
    hasMotionTrail: true,
    hasBatteryStorageStrip: true,
    defaultDetectionChips: ["vessels", "dolphins", "whales"],
    participatesIn: {
      ...ACOUSTIC_SET,
      ...FULL_METOCEAN_SET,
      energy: true,
    },
  },
  "HT-C": {
    key: "HT-C",
    label: "Fixed",
    markerShape: "square",
    hasLiveListen: true,
    hasSpotterPanel: false,
    hasMotionTrail: false,
    hasBatteryStorageStrip: false,
    defaultDetectionChips: ["vessels", "dolphins", "whales"],
    participatesIn: {
      ...ACOUSTIC_SET,
      ...NO_METOCEAN_SET,
      energy: true,
    },
  },
  "HT-V": {
    key: "HT-V",
    label: "Vessel",
    markerShape: "triangle",
    hasLiveListen: true,
    hasSpotterPanel: false,
    hasMotionTrail: true,
    hasBatteryStorageStrip: false,
    defaultDetectionChips: ["vessels", "dolphins", "whales"],
    participatesIn: {
      ...ACOUSTIC_SET,
      ...NO_METOCEAN_SET,
      energy: true,
    },
  },
};

/**
 * Derive the canonical type key from an htId (case-insensitive prefix match).
 * Returns null for unknown formats so callers can guard.
 *
 * @param {string|null|undefined} htId
 * @returns {'HT-S' | 'HT-C' | 'HT-V' | null}
 */
export function getHydrotwinTypeKey(htId) {
  if (!htId) return null;
  const id = String(htId).toLowerCase();
  if (id.startsWith("ht-s")) return "HT-S";
  if (id.startsWith("ht-c")) return "HT-C";
  if (id.startsWith("ht-v")) return "HT-V";
  return null;
}

/**
 * Resolve the full registry entry for an htId.
 *
 * @param {string|null|undefined} htId
 * @returns {(typeof HYDROTWIN_TYPE_REGISTRY)[keyof typeof HYDROTWIN_TYPE_REGISTRY] | null}
 */
export function getHydrotwinTypeMeta(htId) {
  const key = getHydrotwinTypeKey(htId);
  return key ? HYDROTWIN_TYPE_REGISTRY[key] : null;
}

/**
 * Whether a given hydrotwin contributes data to a given chart card.
 * Driven by `participatesIn` so the chart-card pickers stay declarative.
 *
 * @param {string} htId
 * @param {string} cardId — must match an id from constants/siteChartCards.js
 * @returns {boolean}
 */
export function hydrotwinParticipatesIn(htId, cardId) {
  const meta = getHydrotwinTypeMeta(htId);
  if (!meta) return false;
  return Boolean(meta.participatesIn?.[cardId]);
}

/**
 * Type-grouped overlay palettes. Each hydrotwin type gets a hue family so
 * that the colour itself signals the type (HT-S blues, HT-C greens, HT-V
 * ambers). Within a type, the shade is picked by the hydrotwin's position
 * among same-type peers on the site — keeping a given htId's colour stable
 * across every chart on the page.
 *
 * Hex values chosen to pass WCAG-AA contrast against both the light and
 * dark theme surfaces used by the site page.
 */
export const HYDROTWIN_TYPE_PALETTES = {
  //  HT-S (drifting): blue family but spread across hue so 4+ devices stay distinct
  "HT-S": ["#4a8bf0", "#06b6d4", "#8b5cf6", "#22d3ee", "#a78bfa", "#38bdf8"],
  //  HT-C (fixed): green/teal family
  "HT-C": ["#22c55e", "#10b981", "#84cc16", "#34d399", "#a3e635"],
  //  HT-V (vessel): amber/orange/red family
  "HT-V": ["#f59e0b", "#ef4444", "#f97316", "#e879f9", "#fb923c"],
};

/**
 * Flat legacy palette retained so any caller that hasn't been migrated to
 * the object form of `getOverlayColor` continues to work. Derived from the
 * first shade of each type so the brand reads consistently.
 */
export const HYDROTWIN_OVERLAY_PALETTE = [
  ...HYDROTWIN_TYPE_PALETTES["HT-S"].slice(0, 2),
  ...HYDROTWIN_TYPE_PALETTES["HT-C"].slice(0, 2),
  ...HYDROTWIN_TYPE_PALETTES["HT-V"].slice(0, 2),
];

/**
 * Pick a stable overlay colour for a hydrotwin.
 *
 * Two call forms:
 *   getOverlayColor(index)
 *     Legacy form. Indexes into HYDROTWIN_OVERLAY_PALETTE.
 *
 *   getOverlayColor({ htId, scopedHydrotwins })
 *     Type-aware form. Resolves the htId's type (HT-S/HT-C/HT-V), then
 *     picks a shade from the corresponding type palette by the hydrotwin's
 *     position among same-type peers in `scopedHydrotwins`. This is what
 *     keeps the colour mapping stable for a given htId across every chart
 *     on the site page.
 *
 * @returns {string} hex colour
 */
export function getOverlayColor(arg) {
  if (typeof arg === "number") {
    if (!Number.isFinite(arg) || arg < 0) return HYDROTWIN_OVERLAY_PALETTE[0];
    return HYDROTWIN_OVERLAY_PALETTE[arg % HYDROTWIN_OVERLAY_PALETTE.length];
  }
  const { htId, scopedHydrotwins = [] } = arg ?? {};
  const typeKey = getHydrotwinTypeKey(htId) ?? "HT-S";
  const palette = HYDROTWIN_TYPE_PALETTES[typeKey] ?? HYDROTWIN_TYPE_PALETTES["HT-S"];
  const sameType = scopedHydrotwins.filter(
    (h) => (getHydrotwinTypeKey(h.htId) ?? "HT-S") === typeKey,
  );
  const idx = sameType.findIndex((h) => h.htId === htId);
  return palette[Math.max(0, idx) % palette.length];
}
