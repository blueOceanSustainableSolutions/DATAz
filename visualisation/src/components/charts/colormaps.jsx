/**
 * Colormap helpers for the d3 chart primitives. Lifted from the
 * Project Site View prototype (viridis) and adapted for an Anomaly
 * diverging ramp.
 *
 * Both functions take a normalised value in [0,1] (viridis) or [-1,1]
 * (diverging) and return an `rgb(r,g,b)` string.
 */

const VIRIDIS_STOPS = [
  [68, 1, 84],
  [59, 82, 139],
  [33, 145, 140],
  [94, 201, 98],
  [253, 231, 37],
];

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

/**
 * Sample the viridis ramp at t ∈ [0, 1].
 */
export function viridis(t) {
  const x = clamp(t, 0, 1);
  const f = x * (VIRIDIS_STOPS.length - 1);
  const i = Math.floor(f);
  const frac = f - i;
  const a = VIRIDIS_STOPS[i];
  const b = VIRIDIS_STOPS[Math.min(VIRIDIS_STOPS.length - 1, i + 1)];
  return `rgb(${lerp(a[0], b[0], frac)},${lerp(a[1], b[1], frac)},${lerp(a[2], b[2], frac)})`;
}

/**
 * Diverging blue → off-white → yellow at t ∈ [-1, 1]. Matches the
 * prototype's anomaly heatmap palette.
 */
export function diverging(t) {
  const x = clamp(t, -1, 1);
  if (x >= 0) {
    const r = lerp(220, 250, x);
    const g = lerp(232, 250, x);
    const b = lerp(242, 180, x);
    return `rgb(${r},${g},${b})`;
  }
  const u = -x;
  const r = lerp(220, 15, u);
  const g = lerp(232, 45, u);
  const b = lerp(242, 80, u);
  return `rgb(${r},${g},${b})`;
}

export function getColormap(name) {
  if (name === "diverging") return diverging;
  return viridis;
}
