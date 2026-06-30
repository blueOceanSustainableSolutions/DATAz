/**
 * DetectionChip — stacked card showing AI detection activity for one category.
 * Matches the .hts-chip design: icon → name → activity level.
 *
 * Props:
 *   kind      'vessels' | 'dolphins' | 'whales'
 *   activity  'none' | 'low' | 'medium' | 'high' | null
 */

import { DetectionsIcon } from "@/components/Icons";

const LABELS = { vessels: "Vessels", dolphins: "Dolphins", whales: "Whales" };

// Brand accent — used for icon fill and background tint.
const KIND_COLOR = {
  dolphins: "#00ffe5",
  whales:   "#3235D1",
  vessels:  "#ff7853",
};

// Text-safe variant — #00ffe5 is near-white luminosity and invisible as small text on light bg.
const KIND_TEXT_COLOR = {
  dolphins: "#009980",
  whales:   "#3235D1",
  vessels:  "#ff7853",
};

// Dolphins needs a lower tint so the near-white accent doesn't wash out the bg.
const KIND_TINT = {
  dolphins: 8,
  whales:   16,
  vessels:  16,
};

function isActive(level) {
  return level === "low" || level === "medium" || level === "high";
}

function activityLabel(level) {
  if (level == null || level === "none" || level === 0) return "None";
  if (typeof level !== "string") return String(level);
  return level.charAt(0).toUpperCase() + level.slice(1);
}

const BASE_STYLE = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 3,
  padding: "6px 4px 5px",
  fontSize: 10.5,
  borderRadius: 7,
  flex: 1,
  minWidth: 52,
  transition: "all 0.15s",
};

export default function DetectionChip({ kind, activity }) {
  const active = isActive(activity);
  const accent = KIND_COLOR[kind];
  const textColor = KIND_TEXT_COLOR[kind];
  const tint = KIND_TINT[kind] ?? 16;
  const style = active && accent
    ? { ...BASE_STYLE, background: `color-mix(in srgb, ${accent} ${tint}%, transparent)` }
    : { ...BASE_STYLE, background: "var(--grey-200)" };
  const labelColor = active && textColor ? textColor : "var(--text-secondary)";
  const iconType = kind === "whales" ? "whale" : kind;

  return (
    <div style={style}>
      <span style={{ opacity: 0.9 }}><DetectionsIcon type={iconType} color={active && accent ? accent : "var(--text-secondary)"} /></span>
      <span style={{ fontWeight: 500, fontSize: 10.5, lineHeight: 1, color: labelColor }}>{LABELS[kind] ?? kind}</span>
      <span style={{ fontSize: 8.5, textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.85, lineHeight: 1, color: labelColor }}>
        {activityLabel(activity)}
      </span>
    </div>
  );
}
