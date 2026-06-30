import { useEffect, useRef, useMemo } from "react";
import * as d3 from "d3";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";

const CARDINALS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];

function toCardinal(deg) {
  if (deg == null || !Number.isFinite(deg)) return "";
  const d = ((deg % 360) + 360) % 360;
  return CARDINALS[Math.round(d / 22.5) % 16];
}

// ── Single needle dial ────────────────────────────────────────────────────────

function Dial({ deg, color, label, size = 96 }) {
  const svgRef = useRef(null);

  const normalizedDeg =
    deg != null && Number.isFinite(deg) ? ((deg % 360) + 360) % 360 : null;

  const degRef = useRef(normalizedDeg);
  degRef.current = normalizedDeg;

  // Draw effect — runs only when size or color changes
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const cx      = size / 2;
    const cy      = size / 2;
    const r       = size * 0.42;
    const headLen = r * 0.68;
    const tailLen = r * 0.28;
    const hw      = size * 0.052;
    const shoulY  = -headLen + hw * 2.2;

    svg.append("circle")
      .attr("cx", cx).attr("cy", cy).attr("r", r)
      .attr("fill", "var(--surface)")
      .attr("stroke", "var(--grey-300)")
      .attr("stroke-width", 1);

    [0, 45, 90, 135, 180, 225, 270, 315].forEach((a) => {
      const rad      = ((a - 90) * Math.PI) / 180;
      const isCard   = a % 90 === 0;
      const innerEnd = r - (isCard ? r * 0.22 : r * 0.12);
      svg.append("line")
        .attr("x1", cx + Math.cos(rad) * innerEnd)
        .attr("y1", cy + Math.sin(rad) * innerEnd)
        .attr("x2", cx + Math.cos(rad) * r)
        .attr("y2", cy + Math.sin(rad) * r)
        .attr("stroke", "var(--grey-300)")
        .attr("stroke-width", isCard ? 1.5 : 0.75);
    });

    [
      { a: -90, lbl: "N" },
      { a: 0,   lbl: "E" },
      { a: 90,  lbl: "S" },
      { a: 180, lbl: "W" },
    ].forEach(({ a, lbl }) => {
      const rad  = (a * Math.PI) / 180;
      const dist = r * 0.62;
      svg.append("text")
        .attr("x", cx + Math.cos(rad) * dist)
        .attr("y", cy + Math.sin(rad) * dist)
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "middle")
        .attr("font-size", Math.round(size * 0.10))
        .attr("fill", lbl === "N" ? color : "var(--text-secondary)")
        .attr("font-weight", lbl === "N" ? 700 : 400)
        .text(lbl);
    });

    const needle = svg.append("g")
      .attr("transform", `translate(${cx},${cy})`)
      .append("g")
      .attr("class", "compass-needle")
      .attr("transform", `rotate(${degRef.current ?? 0})`);

    needle.append("polygon")
      .attr("points", `0,${-headLen} ${hw},${shoulY} ${-hw},${shoulY}`)
      .attr("fill", color);

    needle.append("rect")
      .attr("x", -hw * 0.45).attr("y", shoulY)
      .attr("width", hw * 0.9)
      .attr("height", Math.abs(shoulY) - headLen * 0.05 + tailLen)
      .attr("fill", color).attr("rx", 1);

    needle.append("polygon")
      .attr("points", `${-hw * 0.8},${tailLen} 0,${tailLen - hw * 1.4} ${hw * 0.8},${tailLen}`)
      .attr("fill", color).attr("opacity", 0.4);

    needle.append("circle").attr("r", hw * 0.9).attr("fill", "var(--surface)");
    needle.append("circle").attr("r", hw * 0.45).attr("fill", color);

  }, [size, color]); // eslint-disable-line react-hooks/exhaustive-deps

  // Rotate effect — transitions needle on every deg change, no full redraw
  useEffect(() => {
    d3.select(svgRef.current)
      .select("g.compass-needle")
      .transition()
      .duration(180)
      .ease(d3.easeQuadOut)
      .attr("transform", `rotate(${normalizedDeg ?? 0})`);
  }, [normalizedDeg]);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <svg
        ref={svgRef}
        width={size} height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ display: "block", overflow: "visible" }}
        aria-hidden="true"
      />
      <div style={{ textAlign: "center", lineHeight: 1.4 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>
          {normalizedDeg != null ? `${Math.round(normalizedDeg)}° ${toCardinal(normalizedDeg)}` : "—"}
        </div>
        <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>{label}</div>
      </div>
    </div>
  );
}

// ── Strip of dials ────────────────────────────────────────────────────────────

/**
 * CompassDial — renders one animated compass per hydrotwin in a horizontal strip.
 *
 * Props:
 *   seriesData        Array<{ htId, readings: Array<Record<string, any>> }>
 *   scopedHydrotwins  Array passed to getOverlayColor for stable color assignment
 *   hoveredDeg        { [htId]: number } | null — values at the hovered chart time
 *   isLoading         boolean
 *   directionKey      string — readings field holding the direction in degrees (default: "meanDirection")
 */
export default function CompassDial({ seriesData = [], scopedHydrotwins = [], hoveredDeg, isLoading, directionKey = "meanDirection" }) {
  const lastDegByHt = useMemo(() => {
    const map = {};
    for (const s of seriesData) {
      const valid = s.readings.filter(
        (r) => r[directionKey] != null && Number.isFinite(r[directionKey]),
      );
      if (valid.length > 0) map[s.htId] = valid[valid.length - 1][directionKey];
    }
    return map;
  }, [seriesData, directionKey]);

  const hasData = seriesData.some((s) =>
    s.readings.some((r) => r[directionKey] != null && Number.isFinite(r[directionKey])),
  );

  if (isLoading || !hasData) return null;

  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: 24,
      justifyContent: "center",
      marginTop: 16,
      padding: "16px 24px 8px",
      borderTop: "0.5px solid var(--grey-300)",
    }}>
      {seriesData.map((s) => (
        <Dial
          key={s.htId}
          deg={hoveredDeg?.[s.htId] ?? lastDegByHt[s.htId] ?? null}
          color={getOverlayColor({ htId: s.htId, scopedHydrotwins })}
          label={s.htId}
          size={96}
        />
      ))}
    </div>
  );
}
