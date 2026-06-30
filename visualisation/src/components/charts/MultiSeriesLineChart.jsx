import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import Spinner from "@/components/Spinner";
import ChartAlert from "@/components/ChartAlert";

import { useTimezone } from "@/context/TimezoneProvider";
import {
  ChartTooltip,
  ChartTooltipItem,
  ChartTooltipTitle,
} from "@/components/ChartTooltip";

import useResizeObserver from "@/components/charts/useResizeObserver";
import useChartTheme from "@/components/charts/useChartTheme";

/**
 * MultiSeriesLineChart — d3 line chart with N series on a shared time axis,
 * optional dual y-axes, shared crosshair tooltip, and horizontal zoom/pan.
 *
 * Zoom: mouse-wheel to zoom in/out, drag to pan, double-click to reset.
 *
 * Props
 *   series       Array<{
 *     id:         string,
 *     label:      string,
 *     color:      string,
 *     data:       Array<{ t: Date|number|string, v: number|null }>,
 *     yAxisKey?:  'left' | 'right',
 *     style?:     'solid' | 'dashed',
 *     unit?:      string,
 *   }>
 *   xDomain?     [t0, t1]
 *   yScales      { left: { label?, unit?, domain? }, right?: { ... } }
 *   gridlines?   'x' | 'y' | 'both'
 *   height?      number (default 320)
 *   gapThresholdMs?  number (default 1h)
 *   isLoading?   boolean
 *   emptyMessage?  string
 *   error?       string | Error   shows an error overlay (takes precedence over empty/loading)
 */

const MARGIN = { top: 16, right: 56, bottom: 32, left: 56 };
const HOVER_RADIUS_PX = 24;
const SPOTLIGHT_RADIUS_PX = 32;
const DIM_OPACITY = 0.28;
const MIN_END_LABEL_WIDTH = 320;
const END_LABEL_HEIGHT = 14;
const END_LABEL_GAP = 2;
const ANIM_MS = 250;
const FADE_MS = 180;

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e) => setReduced(e.matches);
    if (mq.addEventListener) {
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
    mq.addListener(onChange);
    return () => mq.removeListener(onChange);
  }, []);
  return reduced;
}

function shortenLabel(label) {
  if (!label) return "";
  if (label.startsWith("HT-")) return label.slice(3);
  return label;
}

function toMs(t) {
  if (t == null) return null;
  const d = t instanceof Date ? t : new Date(t);
  const ms = d.getTime();
  return Number.isFinite(ms) ? ms : null;
}

function buildGapped(data, gapThresholdMs) {
  const sorted = (data ?? [])
    .map((d) => ({ t: toMs(d?.t), v: d?.v }))
    .filter((d) => d.t != null && Number.isFinite(Number(d.v)))
    .map((d) => ({ t: d.t, v: Number(d.v) }))
    .sort((a, b) => a.t - b.t);

  if (!sorted.length) return [];

  const out = [];
  let prev = null;
  for (const p of sorted) {
    if (prev != null && p.t - prev > gapThresholdMs) {
      out.push({ t: prev + 1, v: null });
    }
    out.push(p);
    prev = p.t;
  }
  return out;
}

function computeYDomain(series, axisKey, override) {
  if (override) return override;
  const values = [];
  for (const s of series) {
    const ax = s.yAxisKey ?? "left";
    if (ax !== axisKey) continue;
    for (const d of s.data ?? []) {
      const v = Number(d?.v);
      if (Number.isFinite(v)) values.push(v);
    }
  }
  if (!values.length) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [min - 1, max + 1];
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

function computeXDomain(series, override) {
  if (override) {
    return override.map((t) => toMs(t)).filter((t) => t != null);
  }
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of series) {
    for (const d of s.data ?? []) {
      const t = toMs(d?.t);
      if (t != null) {
        if (t < lo) lo = t;
        if (t > hi) hi = t;
      }
    }
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
    const now = Date.now();
    return [now - 60 * 60 * 1000, now];
  }
  if (lo === hi) return [lo - 1000, hi + 1000];
  return [lo, hi];
}

function formatTick(ms, offsetMs) {
  // `ms` may be a Date (time-scale axis ticks) or a number (hover timestamps).
  // Coerce to epoch ms first — `Date + number` stringifies the Date and yields NaN.
  const t = ms instanceof Date ? ms.getTime() : Number(ms);
  const d = new Date(t + offsetMs);
  const pad2 = (n) => String(n).padStart(2, "0");
  return `${pad2(d.getUTCDate())}/${pad2(d.getUTCMonth() + 1)} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
}

function yScaleFor(s, geom) {
  return s.yAxisKey === "right" && geom.yRight ? geom.yRight : geom.yLeft;
}

function makeLinePath(pts, xScale, yScale) {
  return d3
    .line()
    .defined((d) => d.v !== null && Number.isFinite(d.v))
    .x((d) => xScale(d.t))
    .y((d) => yScale(d.v))
    .curve(d3.curveMonotoneX)(pts);
}

export default function MultiSeriesLineChart({
  series = [],
  xDomain,
  yScales = { left: {} },
  gridlines = "both",
  height = 320,
  gapThresholdMs = 60 * 60 * 1000,
  isLoading = false,
  emptyMessage = "No data in the selected range.",
  error = null,
  onHoverChange,
}) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);
  const resetZoomRef = useRef(null);
  const clipIdRef = useRef(`hts-clip-${Math.random().toString(36).slice(2, 8)}`);
  const currentXScaleRef = useRef(null);
  const voronoiRef = useRef({ delaunay: null, points: [] });
  const rebuildVoronoiRef = useRef(() => {});
  const { width } = useResizeObserver(containerRef);
  const theme = useChartTheme();
  const { offsetMs, axisLabel } = useTimezone();
  const reducedMotion = usePrefersReducedMotion();
  const animMs = reducedMotion ? 0 : ANIM_MS;
  const fadeMs = reducedMotion ? 0 : FADE_MS;

  const [hover, setHover] = useState(null);
  const onHoverChangeRef = useRef(onHoverChange);
  onHoverChangeRef.current = onHoverChange;
  useEffect(() => { onHoverChangeRef.current?.(hover); }, [hover]);

  const [isZoomed, setIsZoomed] = useState(false);
  const [spotlightId, setSpotlightId] = useState(null);
  const [hiddenSeriesIds, setHiddenSeriesIds] = useState(() => new Set());
  const [isolatedSeriesId, setIsolatedSeriesId] = useState(null);

  const visibleSeries = useMemo(
    () => series.filter((s) => Array.isArray(s.data) && s.data.length > 0),
    [series],
  );

  const hasData = visibleSeries.length > 0;

  const geom = useMemo(() => {
    if (!width || width < 50) return null;
    const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
    const innerH = Math.max(0, height - MARGIN.top - MARGIN.bottom);
    if (innerW <= 0 || innerH <= 0) return null;

    const [x0, x1] = computeXDomain(visibleSeries, xDomain);
    // Time (UTC) scale, not linear: d3's time ticks land on clock-aligned, uniform
    // intervals (hour/day boundaries) instead of arbitrary epoch-millisecond round
    // numbers — which is what made the axis show "random" times. formatTick applies
    // the selected-timezone offset for the displayed labels.
    const xScale = d3.scaleUtc().domain([x0, x1]).range([0, innerW]);

    const yLeft = d3
      .scaleLinear()
      .domain(computeYDomain(visibleSeries, "left", yScales.left?.domain))
      .nice()
      .range([innerH, 0]);

    const hasRight = visibleSeries.some((s) => s.yAxisKey === "right");
    const yRight = hasRight
      ? d3
          .scaleLinear()
          .domain(
            computeYDomain(visibleSeries, "right", yScales.right?.domain),
          )
          .nice()
          .range([innerH, 0])
      : null;

    return { innerW, innerH, xScale, yLeft, yRight };
  }, [width, height, visibleSeries, xDomain, yScales.left?.domain, yScales.right?.domain]);

  // Series with `pts` (gapped point arrays) pre-attached. This is the
  // canonical data bound to chart paths via `.data(..., s => s.id)`.
  const geomSeries = useMemo(() => {
    if (!geom) return [];
    return visibleSeries.map((s) => ({
      ...s,
      pts: buildGapped(s.data, gapThresholdMs),
    }));
  }, [visibleSeries, gapThresholdMs, geom]);

  // Stable string key of the current series ID set. When this changes the
  // picker selection has shifted — reset chart-local visibility state so the
  // picker is the source of truth for "in scope."
  const seriesIdsKey = useMemo(
    () => visibleSeries.map((s) => s.id).sort().join(""),
    [visibleSeries],
  );

  useEffect(() => {
    setHiddenSeriesIds(new Set());
    setIsolatedSeriesId(null);
  }, [seriesIdsKey]);

  // ── STRUCTURE EFFECT ────────────────────────────────────────────────────────
  // Builds axes, gridlines, clip-path, root group, capture rect and zoom
  // behaviour. Mounts the empty `<g class="hts-d3-lines">`, crosshair, and
  // hover-dots groups that the lines and interaction effects populate.
  useEffect(() => {
    if (!geom) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    setIsZoomed(false);
    currentXScaleRef.current = geom.xScale;

    const clipId = clipIdRef.current;
    svg
      .append("defs")
      .append("clipPath")
      .attr("id", clipId)
      .append("rect")
      .attr("width", geom.innerW)
      .attr("height", geom.innerH);

    const g = svg
      .append("g")
      .attr("class", "hts-d3-root")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    function styleAxis(sel) {
      sel.selectAll("text").attr("fill", theme.textSecondary).attr("font-size", 10);
      sel.selectAll("line").attr("stroke", theme.textSecondary);
      sel.selectAll("path").attr("stroke", theme.textSecondary);
    }
    function styleGrid(sel) {
      sel.selectAll("line").attr("stroke", theme.grid);
      sel.selectAll("path").attr("stroke", "transparent");
    }

    function makeXAxis(scale) {
      return d3
        .axisBottom(scale)
        .ticks(Math.max(2, Math.floor(geom.innerW / 110)))
        .tickSizeOuter(0)
        .tickFormat((ms) => formatTick(ms, offsetMs));
    }
    function makeXGrid(scale) {
      return d3
        .axisBottom(scale)
        .ticks(Math.max(2, Math.floor(geom.innerW / 110)))
        .tickSize(-geom.innerH)
        .tickFormat(() => "");
    }

    // Gridlines
    let xGridG = null;
    if (gridlines === "x" || gridlines === "both") {
      xGridG = g
        .append("g")
        .attr("class", "hts-d3-grid-x")
        .attr("transform", `translate(0,${geom.innerH})`);
      xGridG.call(makeXGrid(geom.xScale)).call(styleGrid);
    }
    if (gridlines === "y" || gridlines === "both") {
      g.append("g")
        .attr("class", "hts-d3-grid-y")
        .call(
          d3
            .axisLeft(geom.yLeft)
            .ticks(5)
            .tickSize(-geom.innerW)
            .tickFormat(() => ""),
        )
        .call(styleGrid);
    }

    // X axis
    const xAxisG = g
      .append("g")
      .attr("class", "hts-d3-x-axis")
      .attr("transform", `translate(0,${geom.innerH})`);
    xAxisG.call(makeXAxis(geom.xScale)).call(styleAxis);

    // Y left axis (+ label)
    g.append("g")
      .attr("class", "hts-d3-y-left-axis")
      .call(d3.axisLeft(geom.yLeft).ticks(5).tickSizeOuter(0))
      .call(styleAxis);

    if (yScales.left?.label) {
      g.append("text")
        .attr("class", "hts-d3-y-left-label")
        .attr("transform", "rotate(-90)")
        .attr("x", -geom.innerH / 2)
        .attr("y", -MARGIN.left + 14)
        .attr("text-anchor", "middle")
        .attr("fill", theme.textSecondary)
        .attr("font-size", 11)
        .text(
          yScales.left.unit
            ? `${yScales.left.label} (${yScales.left.unit})`
            : yScales.left.label,
        );
    }

    // Y right axis (+ label)
    if (geom.yRight) {
      g.append("g")
        .attr("class", "hts-d3-y-right-axis")
        .attr("transform", `translate(${geom.innerW},0)`)
        .call(d3.axisRight(geom.yRight).ticks(5).tickSizeOuter(0))
        .call(styleAxis);

      if (yScales.right?.label) {
        g.append("text")
          .attr("class", "hts-d3-y-right-label")
          .attr("transform", "rotate(90)")
          .attr("x", geom.innerH / 2)
          .attr("y", -geom.innerW - MARGIN.right + 14)
          .attr("text-anchor", "middle")
          .attr("fill", theme.textSecondary)
          .attr("font-size", 11)
          .text(
            yScales.right.unit
              ? `${yScales.right.label} (${yScales.right.unit})`
              : yScales.right.label,
          );
      }
    }

    // X axis timezone label
    g.append("text")
      .attr("class", "hts-d3-tz-label")
      .attr("x", geom.innerW / 2)
      .attr("y", geom.innerH + MARGIN.bottom - 4)
      .attr("text-anchor", "middle")
      .attr("fill", theme.textSecondary)
      .attr("font-size", 11)
      .text(axisLabel);

    // Stable lines group — populated by the lines effect.
    g.append("g")
      .attr("class", "hts-d3-lines")
      .attr("clip-path", `url(#${clipId})`);

    // Crosshair line
    g.append("line")
      .attr("class", "hts-d3-crosshair")
      .attr("y1", 0)
      .attr("y2", geom.innerH)
      .attr("stroke", theme.textSecondary)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "3 3")
      .attr("opacity", 0);

    // Hover-dots group — populated by the interaction effect.
    g.append("g")
      .attr("class", "hts-d3-hover-dots")
      .attr("clip-path", `url(#${clipId})`);

    // End-of-line labels group (lives in right margin, no clip).
    g.append("g").attr("class", "hts-d3-end-labels");

    // Capture rect — top of the stack, receives all pointer events.
    const capture = g
      .append("rect")
      .attr("class", "hts-d3-capture")
      .attr("width", geom.innerW)
      .attr("height", geom.innerH)
      .attr("fill", "transparent")
      .style("cursor", "crosshair");

    const zoomBehavior = d3
      .zoom()
      .scaleExtent([1, 40])
      .translateExtent([[0, 0], [geom.innerW, geom.innerH]])
      .extent([[0, 0], [geom.innerW, geom.innerH]])
      .on("start", () => {
        d3.select(svgRef.current)
          .select("g.hts-d3-end-labels")
          .interrupt()
          .transition()
          .duration(fadeMs)
          .attr("opacity", 0);
      })
      .on("end", () => {
        d3.select(svgRef.current)
          .select("g.hts-d3-end-labels")
          .interrupt()
          .transition()
          .duration(fadeMs)
          .attr("opacity", 1);
      })
      .on("zoom", (event) => {
        const next = event.transform.rescaleX(geom.xScale);
        currentXScaleRef.current = next;

        if (xGridG) xGridG.call(makeXGrid(next)).call(styleGrid);
        xAxisG.call(makeXAxis(next)).call(styleAxis);

        // Re-draw lines using bound data (key-stable across re-renders).
        d3.select(svgRef.current)
          .select("g.hts-d3-lines")
          .selectAll("path.hts-line")
          .attr("d", function (s) {
            return makeLinePath(s.pts, next, yScaleFor(s, geom)) ?? "";
          });

        // Hide hover state while zooming/panning.
        d3.select(svgRef.current).select("line.hts-d3-crosshair").attr("opacity", 0);
        d3.select(svgRef.current).select("g.hts-d3-hover-dots").selectAll("*").remove();
        setHover(null);
        setSpotlightId(null);

        // Rebuild voronoi against the new x scale.
        rebuildVoronoiRef.current();

        const zoomed = event.transform.k !== 1 || event.transform.x !== 0;
        setIsZoomed(zoomed);
      });

    capture
      .call(zoomBehavior)
      .on("dblclick.zoom", function () {
        d3.select(this)
          .transition()
          .duration(animMs > 0 ? 300 : 0)
          .call(zoomBehavior.transform, d3.zoomIdentity);
      });

    resetZoomRef.current = () => {
      capture
        .transition()
        .duration(animMs > 0 ? 300 : 0)
        .call(zoomBehavior.transform, d3.zoomIdentity);
    };
  }, [
    geom,
    theme,
    offsetMs,
    axisLabel,
    yScales.left?.label,
    yScales.left?.unit,
    yScales.right?.label,
    yScales.right?.unit,
    gridlines,
    width,
    animMs,
    fadeMs,
  ]);

  // ── LINES EFFECT ────────────────────────────────────────────────────────────
  // Keyed data join over `geomSeries`. Paths persist across re-renders by
  // `s.id`, so add/remove hydrotwins fade in/out instead of teardown.
  useEffect(() => {
    if (!geom) return;
    const linesGroup = d3.select(svgRef.current).select("g.hts-d3-lines");
    if (linesGroup.empty()) return;

    const xScale = currentXScaleRef.current ?? geom.xScale;
    const pathFor = (s) =>
      makeLinePath(s.pts, xScale, yScaleFor(s, geom)) ?? "";

    linesGroup
      .selectAll("path.hts-line")
      .data(geomSeries, (s) => s.id)
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("class", "hts-line")
            .attr("fill", "none")
            .attr("stroke-linejoin", "round")
            .attr("stroke-linecap", "round")
            .attr("stroke", (s) => s.color)
            .attr("stroke-width", 1.75)
            .attr("stroke-dasharray", (s) =>
              s.style === "dashed" ? "5 4" : null,
            )
            .attr("d", pathFor)
            .attr("opacity", 0)
            .call((sel) =>
              sel.transition().duration(animMs).attr("opacity", 1),
            ),
        (update) =>
          update
            .attr("stroke", (s) => s.color)
            .attr("stroke-width", 1.75)
            .attr("stroke-dasharray", (s) =>
              s.style === "dashed" ? "5 4" : null,
            )
            .call((sel) =>
              animMs > 0
                ? sel.transition().duration(animMs).attr("d", pathFor)
                : sel.attr("d", pathFor),
            ),
        (exit) =>
          exit.call((sel) =>
            sel.transition().duration(animMs).attr("opacity", 0).remove(),
          ),
      );
  }, [
    geom,
    geomSeries,
    theme,
    offsetMs,
    axisLabel,
    yScales.left?.label,
    yScales.left?.unit,
    yScales.right?.label,
    yScales.right?.unit,
    gridlines,
    width,
    animMs,
  ]);

  // ── INTERACTION EFFECT ──────────────────────────────────────────────────────
  // Voronoi-backed nearest-series spotlight + legacy crosshair fallback.
  // Builds a Delaunay index over every visible non-null sample; on hover the
  // nearest point determines the "spotlit" series. When the cursor is too far
  // from any sample (> SPOTLIGHT_RADIUS_PX) we fall back to the legacy "all
  // series at this x" tooltip — which is also the path single-series charts
  // and away-from-data hovers take.
  useEffect(() => {
    if (!geom) return;
    const svg = d3.select(svgRef.current);
    const capture = svg.select("rect.hts-d3-capture");
    if (capture.empty()) return;
    const hoverDotsGroup = svg.select("g.hts-d3-hover-dots");
    const crosshair = svg.select("line.hts-d3-crosshair");

    function rebuildVoronoi() {
      const xScale = currentXScaleRef.current ?? geom.xScale;
      const pts = [];
      geomSeries.forEach((s) => {
        // Skip hidden series and (when isolating) anything not the isolated one
        // so the cursor can't spotlight an invisible line.
        if (hiddenSeriesIds.has(s.id)) return;
        if (isolatedSeriesId != null && s.id !== isolatedSeriesId) return;
        if (!s.pts.length) return;
        for (const p of s.pts) {
          if (p.v === null || !Number.isFinite(p.v)) continue;
          pts.push({
            sid: s.id,
            t: p.t,
            v: p.v,
            color: s.color,
            label: s.label,
            unit: s.unit ?? "",
            yAxisKey: s.yAxisKey,
          });
        }
      });
      if (!pts.length || !d3.Delaunay) {
        voronoiRef.current = { delaunay: null, points: [] };
        return;
      }
      const delaunay = d3.Delaunay.from(
        pts,
        (p) => xScale(p.t),
        (p) => yScaleFor({ yAxisKey: p.yAxisKey }, geom)(p.v),
      );
      voronoiRef.current = { delaunay, points: pts };
    }
    rebuildVoronoi();
    rebuildVoronoiRef.current = rebuildVoronoi;

    function legacyHover(mx) {
      const xScale = currentXScaleRef.current ?? geom.xScale;
      const t = xScale.invert(mx);
      const points = [];
      hoverDotsGroup.selectAll("*").remove();

      geomSeries.forEach((s) => {
        if (hiddenSeriesIds.has(s.id)) return;
        if (isolatedSeriesId != null && s.id !== isolatedSeriesId) return;
        if (!s.pts.length) return;
        const realPts = s.pts.filter((p) => p.v !== null);
        if (!realPts.length) return;
        const bisector = d3.bisector((d) => d.t).left;
        const idx = bisector(realPts, t);
        const prev = realPts[idx - 1];
        const next = realPts[idx];
        const candidate =
          !prev
            ? next
            : !next
              ? prev
              : t - prev.t < next.t - t
                ? prev
                : next;
        if (!candidate) return;
        const px = xScale(candidate.t);
        if (Math.abs(px - mx) > HOVER_RADIUS_PX) return;
        const yScale = yScaleFor(s, geom);
        const py = yScale(candidate.v);
        hoverDotsGroup
          .append("circle")
          .attr("cx", px)
          .attr("cy", py)
          .attr("r", 4)
          .attr("fill", theme.surface)
          .attr("stroke", s.color)
          .attr("stroke-width", 2);
        points.push({
          id: s.id,
          label: s.label,
          color: s.color,
          value: candidate.v,
          unit: s.unit ?? "",
          t: candidate.t,
        });
      });

      if (!points.length) {
        crosshair.attr("opacity", 0);
        setSpotlightId(null);
        setHover(null);
        return;
      }
      crosshair.attr("x1", mx).attr("x2", mx).attr("opacity", 1);
      setSpotlightId(null);

      const tooltipX = Math.min(MARGIN.left + mx + 12, (width || 0) - 200);
      const tooltipY = MARGIN.top + 8;
      setHover({ x: tooltipX, y: tooltipY, t: points[0].t, points });
    }

    function handleMove(event) {
      if (event.buttons === 1 && event.type !== "touchmove") return;

      const [mx, my] = d3.pointer(event, capture.node());
      if (mx < 0 || mx > geom.innerW || my < 0 || my > geom.innerH) {
        crosshair.attr("opacity", 0);
        hoverDotsGroup.selectAll("*").remove();
        setSpotlightId(null);
        setHover(null);
        return;
      }

      const xScale = currentXScaleRef.current ?? geom.xScale;
      const { delaunay, points: vpts } = voronoiRef.current;

      // Try voronoi spotlight first.
      let spot = null;
      if (delaunay && vpts.length) {
        const i = delaunay.find(mx, my);
        const p = vpts[i];
        if (p) {
          const px = xScale(p.t);
          const py = yScaleFor({ yAxisKey: p.yAxisKey }, geom)(p.v);
          const dist = Math.hypot(px - mx, py - my);
          if (dist <= SPOTLIGHT_RADIUS_PX) spot = { p, px, py };
        }
      }

      if (!spot) {
        legacyHover(mx);
        return;
      }

      // Spotlight mode.
      hoverDotsGroup.selectAll("*").remove();
      hoverDotsGroup
        .append("circle")
        .attr("cx", spot.px)
        .attr("cy", spot.py)
        .attr("r", 10)
        .attr("fill", spot.p.color)
        .attr("opacity", 0.18);
      hoverDotsGroup
        .append("circle")
        .attr("cx", spot.px)
        .attr("cy", spot.py)
        .attr("r", 5)
        .attr("fill", theme.surface)
        .attr("stroke", spot.p.color)
        .attr("stroke-width", 2.5);
      crosshair.attr("x1", spot.px).attr("x2", spot.px).attr("opacity", 1);
      setSpotlightId(spot.p.sid);

      // Build tooltip: spotlit first (active=true), others at same time sorted
      // by Euclidean proximity to cursor.
      const t = xScale.invert(mx);
      const others = [];
      geomSeries.forEach((s) => {
        if (s.id === spot.p.sid) return;
        if (hiddenSeriesIds.has(s.id)) return;
        if (isolatedSeriesId != null && s.id !== isolatedSeriesId) return;
        if (!s.pts.length) return;
        const realPts = s.pts.filter((p) => p.v !== null);
        if (!realPts.length) return;
        const bisector = d3.bisector((d) => d.t).left;
        const idx = bisector(realPts, t);
        const prev = realPts[idx - 1];
        const next = realPts[idx];
        const candidate =
          !prev
            ? next
            : !next
              ? prev
              : t - prev.t < next.t - t
                ? prev
                : next;
        if (!candidate) return;
        const px = xScale(candidate.t);
        const py = yScaleFor(s, geom)(candidate.v);
        const dist = Math.hypot(px - mx, py - my);
        others.push({
          id: s.id,
          label: s.label,
          color: s.color,
          value: candidate.v,
          unit: s.unit ?? "",
          t: candidate.t,
          dist,
        });
      });
      others.sort((a, b) => a.dist - b.dist);

      const points = [
        {
          id: spot.p.sid,
          label: spot.p.label,
          color: spot.p.color,
          value: spot.p.v,
          unit: spot.p.unit,
          t: spot.p.t,
          active: true,
        },
        ...others,
      ];

      const tooltipX = Math.min(MARGIN.left + mx + 12, (width || 0) - 200);
      const tooltipY = MARGIN.top + 8;
      setHover({ x: tooltipX, y: tooltipY, t: spot.p.t, points });
    }

    function handleLeave() {
      crosshair.attr("opacity", 0);
      hoverDotsGroup.selectAll("*").remove();
      setSpotlightId(null);
      setHover(null);
    }

    capture
      .on("mousemove", handleMove)
      .on("mouseleave", handleLeave)
      .on("touchstart", handleMove)
      .on("touchmove", handleMove);

    return () => {
      capture
        .on("mousemove", null)
        .on("mouseleave", null)
        .on("touchstart", null)
        .on("touchmove", null);
      rebuildVoronoiRef.current = () => {};
    };
  }, [
    geom,
    geomSeries,
    theme,
    offsetMs,
    axisLabel,
    yScales.left?.label,
    yScales.left?.unit,
    yScales.right?.label,
    yScales.right?.unit,
    gridlines,
    width,
    hiddenSeriesIds,
    isolatedSeriesId,
  ]);

  // ── VISIBILITY EFFECT ───────────────────────────────────────────────────────
  // Single source of truth for path opacity. Combines hidden (legend toggle),
  // isolated (legend shift-click), and spotlight (voronoi hover) — in that
  // priority order. Skips paths that are mid-exit so the fade-out transition
  // isn't interrupted.
  useEffect(() => {
    if (!geom) return;
    const linesGroup = d3.select(svgRef.current).select("g.hts-d3-lines");
    if (linesGroup.empty()) return;
    const liveIds = new Set(geomSeries.map((s) => s.id));
    linesGroup.selectAll("path.hts-line").each(function (s) {
      if (!liveIds.has(s.id)) return; // exiting — let transition handle it
      let op;
      if (hiddenSeriesIds.has(s.id)) op = 0;
      else if (isolatedSeriesId != null && s.id !== isolatedSeriesId) op = 0;
      else if (spotlightId != null && s.id !== spotlightId) op = DIM_OPACITY;
      else op = 1;
      d3.select(this).attr("opacity", op);
    });
  }, [spotlightId, hiddenSeriesIds, isolatedSeriesId, geom, geomSeries]);

  // ── END-OF-LINE LABELS EFFECT ───────────────────────────────────────────────
  // Renders a sticky label per visible series at its last non-null point,
  // anchored in the right margin. Greedy vertical-stack collision; collapses
  // overflow into a "+N more" chip. Skipped for dual-axis charts (right margin
  // is occupied by the right axis ticks) and narrow containers.
  useEffect(() => {
    if (!geom) return;
    const group = d3.select(svgRef.current).select("g.hts-d3-end-labels");
    if (group.empty()) return;
    group.selectAll("*").remove();

    if (geom.yRight) return;
    if (geom.innerW < MIN_END_LABEL_WIDTH) return;
    if (geomSeries.length < 2) return;

    const candidates = [];
    for (const s of geomSeries) {
      if (hiddenSeriesIds.has(s.id)) continue;
      if (isolatedSeriesId != null && s.id !== isolatedSeriesId) continue;
      let last = null;
      for (let i = s.pts.length - 1; i >= 0; i--) {
        const p = s.pts[i];
        if (p.v !== null && Number.isFinite(p.v)) {
          last = p;
          break;
        }
      }
      if (!last) continue;
      const yScale = yScaleFor(s, geom);
      candidates.push({
        id: s.id,
        color: s.color,
        text: shortenLabel(s.label),
        y: yScale(last.v),
      });
    }

    if (!candidates.length) return;

    // Greedy vertical-stack — sort by natural y, push subsequent labels down
    // when they would overlap the previous.
    candidates.sort((a, b) => a.y - b.y);
    const step = END_LABEL_HEIGHT + END_LABEL_GAP;
    for (let i = 1; i < candidates.length; i++) {
      if (candidates[i].y - candidates[i - 1].y < step) {
        candidates[i].y = candidates[i - 1].y + step;
      }
    }

    // Clamp the stack so labels stay within the plot area; collapse overflow.
    const maxY = geom.innerH;
    let visibleCount = candidates.length;
    while (visibleCount > 0 && candidates[visibleCount - 1].y > maxY) {
      visibleCount--;
    }
    const overflow = candidates.length - visibleCount;

    for (let i = 0; i < visibleCount; i++) {
      const c = candidates[i];
      group
        .append("text")
        .attr("class", "hts-d3-end-label")
        .attr("x", geom.innerW + 4)
        .attr("y", c.y)
        .attr("fill", c.color)
        .attr("font-size", 10)
        .attr("font-weight", 500)
        .attr("dominant-baseline", "middle")
        .text(c.text);
    }

    if (overflow > 0) {
      group
        .append("text")
        .attr("class", "hts-d3-end-label-overflow")
        .attr("x", geom.innerW + 4)
        .attr("y", Math.min(geom.innerH - 2, candidates[visibleCount]?.y ?? geom.innerH))
        .attr("fill", theme.textSecondary)
        .attr("font-size", 10)
        .attr("dominant-baseline", "middle")
        .text(`+${overflow}`);
    }
  }, [
    geom,
    geomSeries,
    hiddenSeriesIds,
    isolatedSeriesId,
    theme,
    width,
  ]);

  function handleLegendClick(id, shiftKey) {
    if (shiftKey) {
      // Shift-click — isolate this series (or restore if already isolated).
      setIsolatedSeriesId((prev) => (prev === id ? null : id));
      // Isolating implicitly un-hides the target so it can be seen.
      setHiddenSeriesIds((prev) => {
        if (!prev.has(id)) return prev;
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      return;
    }
    // Click — toggle hidden state for this series.
    setHiddenSeriesIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    // If we just hid the isolated series, drop isolation.
    if (isolatedSeriesId === id) setIsolatedSeriesId(null);
  }

  const legend =
    !isLoading && visibleSeries.length >= 1 ? (
      <div className="flex flex-wrap gap-x-12 gap-y-4 px-4 pt-6 pb-2">
        {visibleSeries.map((s) => {
          const isHidden = hiddenSeriesIds.has(s.id);
          const isIsolated = isolatedSeriesId === s.id;
          const isDimmed = isolatedSeriesId != null && !isIsolated;
          return (
            <button
              key={s.id}
              type="button"
              onClick={(e) => handleLegendClick(s.id, e.shiftKey)}
              className="flex items-center gap-4 cursor-pointer select-none"
              style={{ opacity: isHidden ? 0.4 : isDimmed ? 0.55 : 1 }}
              title="Click to toggle · Shift+Click to isolate"
            >
              <span
                className="flex items-center justify-center rounded-4 border shrink-0"
                style={{
                  width: 14,
                  height: 14,
                  background: isHidden ? "transparent" : s.color,
                  borderColor: s.color,
                }}
              >
                {!isHidden && (
                  <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                    <path
                      d="M1 3.5l2.5 2.5 4.5-5"
                      stroke="white"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </span>
              <span style={{ fontSize: 11, color: theme.textPrimary }}>
                {s.label}
                {isIsolated && (
                  <span
                    className="ml-4"
                    style={{ fontSize: 9, color: theme.textSecondary }}
                  >
                    (isolated)
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    ) : null;

  return (
    <div ref={containerRef} className="w-full">
      <div className="relative" style={{ height }}>
      {!error && isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-8 backdrop-blur-sm bg-surface/60">
          <Spinner isLoading size={32} />
        </div>
      )}
      {!error && !isLoading && !hasData && (
        <div className="absolute inset-0 flex items-center justify-center text-textSecondary copy-small">
          {emptyMessage}
        </div>
      )}
      {error && <ChartAlert error={error} />}

      {isZoomed && (
        <button
          type="button"
          onClick={() => resetZoomRef.current?.()}
          className="absolute z-10 copy-extrasmall text-primary hover:underline"
          style={{ top: MARGIN.top + 4, right: MARGIN.right + 8 }}
        >
          Reset zoom
        </button>
      )}

      <svg
        ref={svgRef}
        width={width || 0}
        height={height}
        style={{ display: "block" }}
        role="img"
      />

      <ChartTooltip
        ref={tooltipRef}
        open={Boolean(hover)}
        position={{ x: hover?.x ?? 0, y: hover?.y ?? 0 }}
      >
        {hover && (
          <>
            <ChartTooltipTitle>
              {formatTick(hover.t, offsetMs)}
            </ChartTooltipTitle>
            {hover.points.map((p) => (
              <ChartTooltipItem
                key={p.id}
                color={p.color}
                label={p.label}
                value={Number.isFinite(p.value) ? p.value.toFixed(2) : "–"}
                unit={p.unit}
                highlight={p.active === true}
                dim={spotlightId != null && !p.active}
              />
            ))}
          </>
        )}
      </ChartTooltip>
      </div>
      {legend}
    </div>
  );
}
