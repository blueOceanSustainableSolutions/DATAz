import { useMemo } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";

export default function TempHumidityChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
}) {
  const series = useMemo(
    () =>
      seriesData.flatMap((s) => {
        const color = getOverlayColor({ htId: s.htId, scopedHydrotwins });
        const base = s.readings
          .filter((r) => r.ingestedAt)
          .map((r) => ({ t: new Date(r.ingestedAt), temp: r.temperature, hum: r.humidity }));

        return [
          {
            id: `${s.htId}:temp`,
            label: `${s.htId} temp`,
            color,
            yAxisKey: "left",
            data: base
              .filter((d) => d.temp != null && Number.isFinite(d.temp))
              .map((d) => ({ t: d.t, v: d.temp })),
          },
          {
            id: `${s.htId}:humidity`,
            label: `${s.htId} humidity`,
            color,
            yAxisKey: "right",
            style: "dashed",
            data: base
              .filter((d) => d.hum != null && Number.isFinite(d.hum))
              .map((d) => ({ t: d.t, v: d.hum })),
          },
        ];
      }),
    [seriesData, scopedHydrotwins],
  );

  return (
    <MultiSeriesLineChart
      series={series}
      yScales={{
        left: { label: "Temperature", unit: "°C" },
        right: { label: "Humidity", unit: "%" },
      }}
      isLoading={isLoading}
      emptyMessage={emptyMessage}
      height={height}
    />
  );
}
