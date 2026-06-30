import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import CompassDial from "@/components/charts/CompassDial";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import SegmentedToggle from "@/components/SegmentedToggle";

const DIRECTION_OPTIONS = [
  { key: "peak", label: "Peak" },
  { key: "mean", label: "Mean" },
];

export default function WaveDirectionChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
  onExtraControls,
}) {
  const [mode, setMode] = useState("mean");
  const [hoveredDeg, setHoveredDeg] = useState(null);

  const onExtraControlsRef = useRef(onExtraControls);
  onExtraControlsRef.current = onExtraControls;

  useEffect(() => {
    onExtraControlsRef.current?.(
      <SegmentedToggle
        options={DIRECTION_OPTIONS}
        value={mode}
        onChange={setMode}
        ariaLabel="Wave direction series"
      />,
    );
  }, [mode]);

  useEffect(() => {
    return () => onExtraControlsRef.current?.(null);
  }, []);

  const directionKey = mode === "peak" ? "peakDirection" : "meanDirection";

  const yScales = useMemo(
    () => ({ left: { label: `${mode === "peak" ? "Peak" : "Mean"} Wave Direction`, unit: "°", domain: [0, 360] } }),
    [mode],
  );

  const series = useMemo(
    () =>
      seriesData.map((s) => ({
        id: s.htId,
        label: s.htId,
        color: getOverlayColor({ htId: s.htId, scopedHydrotwins }),
        data: s.readings
          .filter((r) => r[directionKey] != null && Number.isFinite(r[directionKey]))
          .map((r) => ({ t: new Date(r.ingestedAt), v: r[directionKey] })),
      })),
    [seriesData, scopedHydrotwins, directionKey],
  );

  const handleHoverChange = useCallback((hover) => {
    if (!hover?.points?.length) { setHoveredDeg(null); return; }
    const map = {};
    for (const p of hover.points) {
      if (Number.isFinite(p.value)) map[p.id] = p.value;
    }
    setHoveredDeg(map);
  }, []);

  return (
    <>
      <MultiSeriesLineChart
        series={series}
        yScales={yScales}
        isLoading={isLoading}
        emptyMessage={emptyMessage}
        height={height}
        onHoverChange={handleHoverChange}
      />
      <CompassDial
        seriesData={seriesData}
        scopedHydrotwins={scopedHydrotwins}
        hoveredDeg={hoveredDeg}
        isLoading={isLoading}
        directionKey={directionKey}
      />
    </>
  );
}
