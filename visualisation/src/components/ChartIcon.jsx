/**
 * ChartIcon — small monochrome glyph for chart card headers.
 *
 * Centralises the iconography that the prototype hand-rolled inline so
 * each `siteChartCards.js` entry can reference an icon by name and we
 * keep a single set of strokes/weights.
 *
 * Props:
 *   name        keyof typeof ICONS  (required)
 *   size        number (px, default 16)
 *   extraClass  string?  — Tailwind classes for colour (e.g. "text-grey500")
 *
 * The SVGs are stroked using `currentColor` so the colour is controlled
 * by the parent's text colour (Tailwind text-* classes).
 */

const ICONS = {
  // Acoustic — broadband loudness / SPL
  speaker: (
    <>
      <path d="M3 9v6h4l5 4V5L7 9H3z" />
      <path d="M16 7c2 2 2 8 0 10" />
      <path d="M19 4c4 4 4 12 0 16" />
    </>
  ),
  // Acoustic — frequency bands
  bars: (
    <>
      <line x1="4" y1="20" x2="4" y2="10" />
      <line x1="9" y1="20" x2="9" y2="4" />
      <line x1="14" y1="20" x2="14" y2="13" />
      <line x1="19" y1="20" x2="19" y2="7" />
    </>
  ),
  // Acoustic — spectrogram heatmap
  grid: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="21" y2="15" />
      <line x1="9" y1="3" x2="9" y2="21" />
      <line x1="15" y1="3" x2="15" y2="21" />
    </>
  ),
  // Acoustic — anomaly diverging
  anomaly: (
    <>
      <path d="M3 12l3-3 3 6 3-9 3 6 3-3 3 3" />
    </>
  ),
  // Acoustic — AI detections
  ai: (
    <>
      <path d="M12 3l8 4v6c0 4-3 7-8 8-5-1-8-4-8-8V7l8-4z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  // Metocean — wave height
  wave: (
    <>
      <path d="M2 13c2-3 4-3 6 0s4 3 6 0 4-3 6 0" />
      <path d="M2 18c2-3 4-3 6 0s4 3 6 0 4-3 6 0" />
    </>
  ),
  // Metocean — period
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  // Metocean — direction
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M15 9l-3 9-3-9 6 0z" />
    </>
  ),
  // Metocean — wind
  wind: (
    <>
      <path d="M3 9h11a3 3 0 100-6" />
      <path d="M3 14h15a3 3 0 110 6" />
      <path d="M3 19h8" />
    </>
  ),
  // Metocean — barometric pressure
  gauge: (
    <>
      <path d="M3 14a9 9 0 0118 0" />
      <path d="M12 14l4-4" />
      <circle cx="12" cy="14" r="1" />
    </>
  ),
  // Metocean — dissolved oxygen / water drop
  drop: (
    <>
      <path d="M12 3c4 6 6 9 6 12a6 6 0 11-12 0c0-3 2-6 6-12z" />
    </>
  ),
  // Metocean — current flow
  flow: (
    <>
      <path d="M3 8h14" />
      <path d="M14 5l3 3-3 3" />
      <path d="M3 16h11" />
      <path d="M11 13l3 3-3 3" />
    </>
  ),
  // Metocean — temperature & humidity
  thermometer: (
    <>
      <path d="M10 14V4a2 2 0 014 0v10" />
      <circle cx="12" cy="17" r="3" />
      <line x1="12" y1="14" x2="12" y2="17" />
    </>
  ),
  // System — energy / battery
  battery: (
    <>
      <rect x="2" y="7" width="18" height="10" rx="2" />
      <line x1="22" y1="11" x2="22" y2="13" />
      <line x1="6" y1="10" x2="6" y2="14" />
      <line x1="10" y1="10" x2="10" y2="14" />
      <line x1="14" y1="10" x2="14" y2="14" />
    </>
  ),
};

export default function ChartIcon({ name, size = 16, extraClass = "" }) {
  const inner = ICONS[name];
  if (!inner) return null;
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${extraClass}`}
      aria-hidden="true"
    >
      {inner}
    </svg>
  );
}
