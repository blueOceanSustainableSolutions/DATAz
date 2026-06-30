import { useEffect, useMemo, useState } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import SegmentedToggle from "@/components/SegmentedToggle";

const PERIOD_OPTIONS = [
  { key: "peak", label: "Peak" },
  { key: "mean", label: "Mean" },
];

export default function WavePeriodChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
  onExtraControls,
}) {
  const [mode, setMode] = useState("peak");

  useEffect(() => {
    onExtraControls?.(
      <SegmentedToggle
        options={PERIOD_OPTIONS}
        value={mode}
        onChange={setMode}
        ariaLabel="Wave period series"
      />,
    );
    return () => onExtraControls?.(null);
  }, [mode, onExtraControls]);

  const series = useMemo(
    () => {
      const key = mode === "peak" ? "peakPeriod" : "meanPeriod";
      return seriesData.map((s) => ({
        id: s.htId,
        label: s.htId,
        color: getOverlayColor({ htId: s.htId, scopedHydrotwins }),
        data: s.readings
          .filter((r) => r[key] != null && Number.isFinite(r[key]))
          .map((r) => ({ t: new Date(r.ingestedAt), v: r[key] })),
      }));
    },
    [seriesData, scopedHydrotwins, mode],
  );

  return (
    <MultiSeriesLineChart
      series={series}
      yScales={{ left: { label: "Wave Period", unit: "s" } }}
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
