import { useMemo } from "react";
import FrequencyTimeHeatmap from "@/components/charts/FrequencyTimeHeatmap";
import { siteSplOffset } from "@/lib/charts";

// spectrum.p50 keys are floats-as-strings: "40.0", "63.0", etc.
function lookupP50(spectrum, hz) {
  const p50 = spectrum?.p50;
  if (!p50) return NaN;
  return p50[hz.toFixed(1)] ?? p50[String(hz)] ?? p50[hz] ?? NaN;
}

function buildHeatmapCells(readings, offset = 0) {
  if (!readings || readings.length === 0) return null;

  // Find the first reading that has spectrum.p50 with frequency data.
  const firstWithSpectrum = readings.find(
    (r) => r.spectrum?.p50 && typeof r.spectrum.p50 === "object",
  );
  if (!firstWithSpectrum) return null;

  // Frequency bands are the INNER keys of spectrum.p50 (not the outer percentile keys).
  const freqKeys = Object.keys(firstWithSpectrum.spectrum.p50)
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (freqKeys.length === 0) return null;

  const cols = readings.length;
  const rows = freqKeys.length;
  const freqsDesc = [...freqKeys].reverse(); // y=0 = highest freq (top of heatmap)

  const data = new Float32Array(cols * rows);
  let zMin = Infinity;
  let zMax = -Infinity;

  for (let x = 0; x < cols; x++) {
    const spectrum = readings[x].spectrum;
    for (let y = 0; y < rows; y++) {
      const freq = freqsDesc[y];
      const raw = lookupP50(spectrum, freq);
      // Per-device SPL calibration so the dB scale matches the deployment page.
      const val = Number.isFinite(raw) ? raw + offset : NaN;
      data[y * cols + x] = val;
      if (Number.isFinite(val)) {
        if (val < zMin) zMin = val;
        if (val > zMax) zMax = val;
      }
    }
  }

  const xStep = Math.max(1, Math.ceil(cols / 8));
  const xTicks = readings
    .filter((_, i) => i % xStep === 0)
    .map((r) => ({
      value: new Date(r.ingestedAt),
      label: new Date(r.ingestedAt).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    }));

  const yStep = Math.max(1, Math.ceil(rows / 8));
  const yTicks = freqsDesc.filter((_, i) => i % yStep === 0).map((f) => ({
    value: f,
    label: f >= 1000 ? `${(f / 1000).toFixed(f % 1000 === 0 ? 0 : 1)}k` : String(f),
  }));

  // Per-column timestamps (ms) — aligns with the column order above so the
  // heatmap can place each reading on a real time scale.
  const colTimes = readings.map((r) => new Date(r.ingestedAt).getTime());

  return {
    data,
    cols,
    rows,
    xTicks,
    yTicks,
    colTimes,
    zDomain: [zMin === Infinity ? 0 : zMin, zMax === -Infinity ? 1 : zMax],
  };
}

export default function SpectrogramChart({
  seriesData = [],
  startDate,
  endDate,
  isLoading,
  emptyMessage,
  height,
}) {
  const heatmap = useMemo(() => {
    const s = seriesData[0];
    return buildHeatmapCells(s?.readings ?? [], siteSplOffset(s?.htId));
  }, [seriesData]);

  const xDomain = useMemo(() => {
    if (!startDate || !endDate) return null;
    const t0 = new Date(startDate).getTime();
    const t1 = new Date(endDate).getTime();
    return Number.isFinite(t0) && Number.isFinite(t1) ? [t0, t1] : null;
  }, [startDate, endDate]);

  return (
    <FrequencyTimeHeatmap
      cells={heatmap?.data ?? null}
      cols={heatmap?.cols ?? 0}
      rows={heatmap?.rows ?? 0}
      xTicks={heatmap?.xTicks ?? []}
      yTicks={heatmap?.yTicks ?? []}
      xDomain={xDomain}
      colTimes={heatmap?.colTimes ?? null}
      colorScale="viridis"
      zDomain={heatmap?.zDomain ?? [0, 1]}
      zUnitLabel="SPL (dB)"
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
