import { useEffect, useMemo, useRef, useState } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import SegmentedToggle from "@/components/SegmentedToggle";

const DO_OPTIONS = [
  { key: "concentration", label: "Oxygen Concentration" },
  { key: "quality", label: "Quality Factor" },
];

const Y_SCALES = {
  concentration: { left: { label: "Dissolved Oxygen", unit: "mg/L" } },
  quality: { left: { label: "Quality Factor", unit: "" } },
};

export default function DissolvedOxygenChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
  onExtraControls,
}) {
  // Default view is oxygen concentration; "Quality Factor" plots the
  // qualityFactor field already returned alongside each reading.
  const [mode, setMode] = useState("concentration");

  const onExtraControlsRef = useRef(onExtraControls);
  onExtraControlsRef.current = onExtraControls;

  useEffect(() => {
    onExtraControlsRef.current?.(
      <SegmentedToggle
        options={DO_OPTIONS}
        value={mode}
        onChange={setMode}
        ariaLabel="Dissolved oxygen series"
      />,
    );
  }, [mode]);

  useEffect(() => {
    return () => onExtraControlsRef.current?.(null);
  }, []);

  const series = useMemo(() => {
    const key = mode === "quality" ? "qualityFactor" : "dissolvedOxygen";
    return seriesData.map((s) => ({
      id: s.htId,
      label: s.htId,
      color: getOverlayColor({ htId: s.htId, scopedHydrotwins }),
      data: s.readings
        .filter((r) => r[key] != null && Number.isFinite(r[key]))
        .map((r) => ({ t: new Date(r.ingestedAt), v: r[key] })),
    }));
  }, [seriesData, scopedHydrotwins, mode]);

  return (
    <MultiSeriesLineChart
      series={series}
      yScales={Y_SCALES[mode]}
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
