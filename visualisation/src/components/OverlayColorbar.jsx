import { overlayGradientCss } from "@/constants/numericalOverlay";

/**
 * OverlayColorbar — legend for a map-overlay's colour scale.
 *
 * Reads the scale straight from the manifest so the bar always matches the range the
 * frames were rendered with. Cyclic direction variables (0–360°, degree units) get a
 * cyclic colormap + compass-style quarter ticks; magnitude variables get min/mid/max.
 */
export default function OverlayColorbar({ colorScale, variable }) {
  if (!colorScale) return null;
  const { vmin, vmax, colormap, mode } = colorScale;
  const perFrame = mode === "per-frame" || vmin == null || vmax == null;
  const fmt = (n) => (Number.isInteger(n) ? n : Number(n).toFixed(1));

  const isDirection =
    (variable?.units || "").toLowerCase().startsWith("degree") &&
    vmin === 0 &&
    vmax === 360;

  const ticks = perFrame
    ? []
    : isDirection
      ? [0, 90, 180, 270, 360]
      : [vmin, (vmin + vmax) / 2, vmax];

  return (
    <div
      className="pointer-events-none select-none rounded-8 border border-grey300 bg-surface px-12 py-10 shadow-sm"
      style={{ minWidth: 168 }}
    >
      <div className="copy-extrasmall font-semibold uppercase tracking-wide text-textPrimary">
        {variable?.long_name || variable?.name || "value"}
        {variable?.units ? (
          <span className="text-grey500"> ({variable.units})</span>
        ) : null}
      </div>

      <div
        className="my-8 h-8 w-full rounded-4"
        style={{ background: overlayGradientCss(colormap) }}
      />

      <div className="flex justify-between">
        {perFrame ? (
          <span className="copy-extrasmall text-grey500">per-frame auto-stretch</span>
        ) : (
          ticks.map((t, i) => (
            <span key={i} className="copy-extrasmall text-grey500">
              {fmt(t)}
            </span>
          ))
        )}
      </div>

      <div className="mt-4 copy-extrasmall text-grey400">
        {perFrame ? "" : isDirection ? " · cyclic 0–360°" : ""}
      </div>
    </div>
  );
}
