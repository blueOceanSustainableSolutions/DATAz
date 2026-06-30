import { useMemo } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";

export default function BarometerChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
}) {
  const series = useMemo(
    () =>
      seriesData.map((s) => ({
        id: s.htId,
        label: s.htId,
        color: getOverlayColor({ htId: s.htId, scopedHydrotwins }),
        data: s.readings.map((r) => ({ t: new Date(r.ingestedAt), v: r.pressure })),
      })),
    [seriesData, scopedHydrotwins],
  );

  return (
    <MultiSeriesLineChart
      series={series}
      yScales={{ left: { label: "Barometric Pressure", unit: "hPa" } }}
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
