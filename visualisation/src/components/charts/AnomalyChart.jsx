import { useMemo } from "react";
import FrequencyTimeHeatmap from "@/components/charts/FrequencyTimeHeatmap";
import { shouldUseStandardPercentiles } from "@/constants/scoutConfig";

// Read a frequency's value from the chosen percentile band (p50 for modern
// devices, p99m for the legacy HT-S units — matches the deployment anomaly chart).
function lookupPctl(spectrum, hz, pctKey) {
  const band = spectrum?.[pctKey];
  if (!band) return NaN;
  return band[hz.toFixed(1)] ?? band[String(hz)] ?? band[hz] ?? NaN;
}

function buildAnomalyCells(readings, pctKey) {
  if (!readings || readings.length === 0) return null;

  const firstWithSpectrum = readings.find(
    (r) => r.spectrum?.[pctKey] && typeof r.spectrum[pctKey] === "object",
  );
  if (!firstWithSpectrum) return null;

  const freqKeys = Object.keys(firstWithSpectrum.spectrum[pctKey])
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (freqKeys.length === 0) return null;

  const cols = readings.length;
  const rows = freqKeys.length;
  const freqsDesc = [...freqKeys].reverse();

  // Build raw SPL matrix (rows = freq desc, cols = time)
  const raw = new Float32Array(cols * rows);
  for (let x = 0; x < cols; x++) {
    const spectrum = readings[x].spectrum;
    for (let y = 0; y < rows; y++) {
      const val = lookupPctl(spectrum, freqsDesc[y], pctKey);
      raw[y * cols + x] = Number.isFinite(val) ? val : NaN;
    }
  }

  // Subtract per-frequency time-mean to get ΔSPL
  const data = new Float32Array(cols * rows);
  for (let y = 0; y < rows; y++) {
    let sum = 0;
    let count = 0;
    for (let x = 0; x < cols; x++) {
      const v = raw[y * cols + x];
      if (Number.isFinite(v)) { sum += v; count++; }
    }
    const mean = count > 0 ? sum / count : 0;
    for (let x = 0; x < cols; x++) {
      const v = raw[y * cols + x];
      data[y * cols + x] = Number.isFinite(v) ? v - mean : NaN;
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

  const colTimes = readings.map((r) => new Date(r.ingestedAt).getTime());

  return { data, cols, rows, xTicks, yTicks, colTimes };
}

export default function AnomalyChart({
  seriesData = [],
  startDate,
  endDate,
  isLoading,
  emptyMessage,
  height,
}) {
  const heatmap = useMemo(() => {
    const s = seriesData[0];
    // p50 for modern devices, p99m for legacy HT-S — same rule as the deployment
    // AnnomalySummary so the same unit's anomaly matches. (The SPL offset cancels
    // in ΔSPL = value − per-frequency mean, so no offset is applied here.)
    const pctKey = shouldUseStandardPercentiles(s?.htId) ? "p50" : "p99m";
    return buildAnomalyCells(s?.readings ?? [], pctKey);
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
      colorScale="diverging"
      zDomain={[-20, 20]}
      zUnitLabel="ΔSPL (dB)"
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
