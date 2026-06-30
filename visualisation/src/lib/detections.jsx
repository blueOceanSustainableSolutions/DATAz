import { DETECTION_DISPLAY_NAMES } from "@/constants/scoutConfig";

// ── Category presentation ──────────────────────────────────────────────────
// Colors, hex values, and display labels for detection categories.

export function getCategoryColor(categoryId) {
  const id = String(categoryId || "").toLowerCase();
  const map = {
    vessels: "var(--chart-blue)",
    vessel: "var(--chart-blue)",
    dolphins: "var(--chart-green)",
    dolphin: "var(--chart-green)",
    whale: "var(--chart-purple)",
    whales: "var(--chart-purple)",
    hfv: "var(--chart-blue)",
    mfv: "var(--chart-purple)",
    lfv: "var(--chart-green-dark)",
  };
  return map[id] || "var(--chart-base)";
}

export function getCategoryHex(categoryId) {
  const id = String(categoryId || "").toLowerCase();
  const map = {
    vessels: "#3989f9",
    vessel: "#3989f9",
    dolphins: "#38bc72",
    dolphin: "#38bc72",
    whale: "#8366ee",
    whales: "#8366ee",
    hfv: "#3989f9",
    mfv: "#8366ee",
    lfv: "#309f60",
  };
  return map[id] || "#546666";
}

export function getCategoryLabel(categoryId) {
  const id = String(categoryId || "").toLowerCase();
  if (DETECTION_DISPLAY_NAMES[id]) {
    return DETECTION_DISPLAY_NAMES[id];
  }
  if (!id) return "—";
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Detection chart helpers ────────────────────────────────────────────────
// Merge API data with defaults and sort for display.

export const RECENT_DETECTIONS_LIMIT = 10;

export const RECENT_FILTER_ALL = "all";
export const RECENT_FILTER_VESSELS = "vessels";
export const RECENT_FILTER_MAMMALS = "mammals";

const VESSEL_SLUGS = new Set([
  "vessels",
  "vessel",
  "hfv",
  "mfv",
  "lfv",
]);

const MAMMAL_SLUGS = new Set([
  "dolphins",
  "dolphin",
  "whale",
  "whales",
]);

export function formatTimeAgo(iso, nowMs = Date.now()) {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const diffSec = Math.max(0, Math.floor((nowMs - t) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) {
    const remMin = diffMin % 60;
    return remMin === 0 ? `${diffHr}h ago` : `${diffHr}h ${remMin}m ago`;
  }
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function formatExactUtcTimeSubline(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(11, 19);
}

export function getSplDb(row) {
  const raw = row?.splDb ?? row?.spl_db;
  if (raw === null || raw === undefined || raw === "") return null;
  const n = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function normaliseCategory(category) {
  return String(category || "").toLowerCase();
}

export function passesRecentFilter(filterId, category) {
  const cat = normaliseCategory(category);
  if (filterId === RECENT_FILTER_ALL || !filterId) return true;
  if (filterId === RECENT_FILTER_VESSELS) return VESSEL_SLUGS.has(cat);
  if (filterId === RECENT_FILTER_MAMMALS) return MAMMAL_SLUGS.has(cat);
  return true;
}

// ── Binned aggregates ──────────────────────────────────────────────────────
// Processing, ordering, and formatting for the binned time-series heatmap.

const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const CATEGORY_SORT_RANK = {
  hfv: 0,
  mfv: 1,
  lfv: 2,
  vessels: 3,
  vessel: 3,
  dolphins: 4,
  dolphin: 4,
  whales: 5,
  whale: 5,
};

export function rankCategory(cat) {
  const id = String(cat || "").toLowerCase();
  return CATEGORY_SORT_RANK[id] ?? 100;
}

export function buildGlobalCategoryOrder(bins) {
  const totals = new Map();
  for (const bin of bins || []) {
    for (const c of bin.categories || []) {
      const key = String(c.category || "").toLowerCase();
      totals.set(
        key,
        (totals.get(key) || 0) + (Number(c.events) || 0),
      );
    }
  }
  return [...totals.entries()]
    .sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return rankCategory(a[0]) - rankCategory(b[0]);
    })
    .map(([k]) => k);
}

export function formatBinTooltipRange(binStart, binEnd) {
  const a = new Date(binStart);
  const b = new Date(binEnd);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return "—";
  const sameDay =
    a.getUTCFullYear() === b.getUTCFullYear() &&
    a.getUTCMonth() === b.getUTCMonth() &&
    a.getUTCDate() === b.getUTCDate();

  const pad = (n) => String(n).padStart(2, "0");
  const t = (d) =>
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;

  if (sameDay) {
    const dateStr = `${MONTHS_SHORT[a.getUTCMonth()]} ${a.getUTCDate()}, ${a.getUTCFullYear()}`;
    return `${dateStr} · ${t(a)}–${t(b)} UTC`;
  }
  return `${a.toISOString().slice(0, 19).replace("T", " ")} → ${b.toISOString().slice(0, 19).replace("T", " ")} UTC`;
}

export function getCategoryCell(bin, categoryKey) {
  const want = String(categoryKey || "").toLowerCase();
  for (const c of bin?.categories || []) {
    if (String(c.category || "").toLowerCase() === want) return c;
  }
  return null;
}

export function getAdaptiveBinMinutes(startMs, endMs) {
  const hours = (endMs - startMs) / 3_600_000;
  if (hours <= 6) return 5;
  if (hours <= 24) return 15;
  if (hours <= 72) return 60;
  if (hours <= 168) return 180;
  if (hours <= 720) return 360;
  return 1440;
}

export function formatBinWidthLabel(binMinutes) {
  const n = Number(binMinutes);
  if (!Number.isFinite(n)) return "—";
  if (n >= 10080) return `${n / 10080}w`;
  if (n >= 1440)  return `${n / 1440}d`;
  if (n >= 60)    return `${n / 60}h`;
  return `${n}min`;
}

/** ISO string for the start of the detections window. */
export function detectionsStartIso(dateStart) {
  return new Date(dateStart).toISOString();
}

/**
 * ISO string for the end of the detections window.
 *  - end date is today (UTC) → clamp to the current minute (never query the
 *    future; two callers within the same minute produce the identical string).
 *  - end date is a past day → extend to the end of that UTC day.
 *  - unparseable → fall back to now.
 */
export function detectionsEndIso(dateEnd) {
  const today = new Date();
  const endDateObj = new Date(dateEnd);
  if (Number.isNaN(endDateObj.getTime())) {
    today.setUTCSeconds(0, 0);
    return today.toISOString();
  }
  const isEndDateToday =
    endDateObj.getUTCFullYear() === today.getUTCFullYear() &&
    endDateObj.getUTCMonth() === today.getUTCMonth() &&
    endDateObj.getUTCDate() === today.getUTCDate();
  if (isEndDateToday) {
    today.setUTCSeconds(0, 0);
    return today.toISOString();
  }
  endDateObj.setUTCHours(23, 59, 59, 999);
  return endDateObj.toISOString();
}

/** True when the ISO timestamp's UTC date equals today's UTC date. */
export function rangeIncludesToday(isoString) {
  const d = new Date(isoString);
  const now = new Date();
  return (
    d.getUTCFullYear() === now.getUTCFullYear() &&
    d.getUTCMonth() === now.getUTCMonth() &&
    d.getUTCDate() === now.getUTCDate()
  );
}
