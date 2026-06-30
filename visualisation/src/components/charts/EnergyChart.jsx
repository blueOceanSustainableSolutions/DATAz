import { useEffect, useMemo, useState } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import SegmentedToggle from "@/components/SegmentedToggle";

const ENERGY_OPTIONS = [
  { key: "battery", label: "Battery" },
  { key: "solar", label: "Solar" },
];

export default function EnergyChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
  onExtraControls,
}) {
  const [mode, setMode] = useState("battery");

  useEffect(() => {
    onExtraControls?.(
      <SegmentedToggle
        options={ENERGY_OPTIONS}
        value={mode}
        onChange={setMode}
        ariaLabel="Energy series"
      />,
    );
    return () => onExtraControls?.(null);
  }, [mode, onExtraControls]);

  const series = useMemo(
    () => {
      const key = mode === "battery" ? "batteryVoltage" : "solarVoltage";
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
      yScales={{ left: { label: mode === "battery" ? "Battery Voltage" : "Solar Voltage", unit: "V" } }}
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
