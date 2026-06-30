import { STATUS_LABELS, STATUS_CSS_VAR } from "@/constants/statusConfig";

/**
 * Inline pill for a hydrotwin's operational status. Colour uses the same
 * --chart-* / --error / --grey-* tokens the rest of the app uses for
 * that status, tinted via CSS color-mix() so it themes automatically.
 *
 * Props:
 *   status      string  — one of STATUS_LABELS keys
 *   size        'sm'|'md'  — default 'md'
 *   extraClass  string?
 */

const SIZE_CLASSES = {
  sm: "px-8 py-2 copy-extrasmall gap-x-4",
  md: "px-10 py-4 copy-small gap-x-6",
};

const DOT_SIZE = {
  sm: 6,
  md: 8,
};

export default function StatusPill({
  status,
  size = "md",
  extraClass = "",
}) {
  const key = status ? String(status).toLowerCase() : "";
  const label = STATUS_LABELS[key] ?? (status ? status.replace(/_/g, " ") : "");
  const cssVar = STATUS_CSS_VAR[key] ?? "--grey-400";
  const color = `var(${cssVar})`;
  // 18% tint over the surface so the pill keeps decent contrast in
  // both light and dark themes. color-mix is widely supported in
  // evergreen browsers (Chrome 111+, Safari 16.2+, Firefox 113+).
  const background = `color-mix(in srgb, var(${cssVar}) 18%, transparent)`;
  const dotPx = DOT_SIZE[size];

  return (
    <span
      className={`inline-flex items-center rounded-8 font-medium whitespace-nowrap ${SIZE_CLASSES[size]} ${extraClass}`}
      style={{ background, color }}
    >
      <span
        className="rounded-full shrink-0"
        style={{ width: dotPx, height: dotPx, background: color }}
      />
      {label}
    </span>
  );
}
