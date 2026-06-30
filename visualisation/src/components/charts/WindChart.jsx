import { useEffect, useMemo, useState, useCallback } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import CompassDial from "@/components/charts/CompassDial";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import SegmentedToggle from "@/components/SegmentedToggle";

const WIND_OPTIONS = [
  { key: "speed", label: "Speed" },
  { key: "direction", label: "Direction" },
];

export default function WindChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
  onExtraControls,
}) {
  const [mode, setMode] = useState("speed");
  const [hoveredDeg, setHoveredDeg] = useState(null);

  useEffect(() => {
    onExtraControls?.(
      <SegmentedToggle
        options={WIND_OPTIONS}
        value={mode}
        onChange={setMode}
        ariaLabel="Wind series"
      />,
    );
    return () => onExtraControls?.(null);
  }, [mode, onExtraControls]);

  const series = useMemo(() => {
    const isDir = mode === "direction";
    return seriesData.map((s) => ({
      id: s.htId,
      label: s.htId,
      color: getOverlayColor({ htId: s.htId, scopedHydrotwins }),
      data: s.readings
        .filter((r) => r[isDir ? "direction" : "speed"] != null && Number.isFinite(r[isDir ? "direction" : "speed"]))
        .map((r) => ({ t: new Date(r.ingestedAt), v: r[isDir ? "direction" : "speed"] })),
    }));
  }, [seriesData, scopedHydrotwins, mode]);

  const handleHoverChange = useCallback((hover) => {
    if (!hover?.points?.length) { setHoveredDeg(null); return; }
    const map = {};
    for (const p of hover.points) {
      if (Number.isFinite(p.value)) map[p.id] = p.value;
    }
    setHoveredDeg(map);
  }, []);

  const isDirection = mode === "direction";

  return (
    <>
      <MultiSeriesLineChart
        series={series}
        yScales={{
          left: {
            label: isDirection ? "Wind Direction" : "Wind Speed",
            unit: isDirection ? "°" : "m/s",
            ...(isDirection && { domain: [0, 360] }),
          },
        }}
        isLoading={isLoading}
        emptyMessage={emptyMessage}
        height={height}
        onHoverChange={isDirection ? handleHoverChange : undefined}
      />
      {isDirection && (
        <CompassDial
          seriesData={seriesData}
          scopedHydrotwins={scopedHydrotwins}
          hoveredDeg={hoveredDeg}
          isLoading={isLoading}
          directionKey="direction"
        />
      )}
    </>
  );
}
