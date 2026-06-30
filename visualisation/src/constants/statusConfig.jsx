/**
 * Single source of truth for status labels and colours.
 *
 * STATUS_LABELS  — human-readable strings for all status keys.
 * STATUS_HEX     — fixed hex colours for canvas/SVG drawing (map icons, badges).
 *                  These are not theme-aware by design; canvas APIs require absolute
 *                  colour values.
 * STATUS_CSS_VAR — CSS custom-property names for themed HTML components; colour
 *                  resolves automatically in light/dark mode.
 */

export const STATUS_LABELS = {
  active:         "Active",
  low_battery:    "Low Battery",
  charging:       "Charging",
  unresponsive:   "Unresponsive",
  maintenance:    "Maintenance",
  decommissioned: "Decommissioned",
};

export const STATUS_HEX = {
  active:         "#38BC72",
  low_battery:    "#FC8923",
  charging:       "#3A7BD5",
  unresponsive:   "#EC4D4D",
  maintenance:    "#B5B8B8",
  decommissioned: "#777979",
};

export const STATUS_CSS_VAR = {
  active:         "--chart-green",
  low_battery:    "--chart-orange",
  charging:       "--chart-blue",
  unresponsive:   "--error",
  maintenance:    "--grey-400",
  decommissioned: "--grey-500",
};
