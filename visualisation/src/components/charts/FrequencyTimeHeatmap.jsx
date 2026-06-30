import { useEffect, useMemo, useRef, useState } from "react";
import Spinner from "@/components/Spinner";
import ChartAlert from "@/components/ChartAlert";
import { useTimezone } from "@/context/TimezoneProvider";

import {
  ChartTooltip,
  ChartTooltipTitle,
} from "@/components/ChartTooltip";

import useResizeObserver from "@/components/charts/useResizeObserver";
import useChartTheme from "@/components/charts/useChartTheme";
import { getColormap } from "@/components/charts/colormaps";

const X_TICK_COUNT = 6;

function pad2(n) {
  return String(n).padStart(2, "0");
}

// Mirrors MultiSeriesLineChart.formatTick so the heatmap's x-axis labels read
// identically to the line charts (same timezone offset, same DD/MM HH:MM form).
function formatTimeTick(ms, offsetMs) {
  const d = new Date(ms + offsetMs);
  return `${pad2(d.getUTCDate())}/${pad2(d.getUTCMonth() + 1)} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
}

/**
 * FrequencyTimeHeatmap — d3 / canvas heatmap on a frequency × time grid.
 *
 * Used by Spectrogram (viridis, absolute SPL dB) and Anomaly summary
 * (diverging, ΔSPL). Single-hydrotwin only (the chart card's picker
 * enforces `mode: 'single'`).
 *
 * Props
 *   cells        Float32Array | number[]   length = cols * rows; row-major
 *                                          (cells[y*cols + x]); OR
 *                {
 *                  cols: number,
 *                  rows: number,
 *                  valueAt(x, y): number,
 *                }
 *   cols         number   (required if `cells` is a typed array)
 *   rows         number   (required if `cells` is a typed array)
 *   xTicks       Array<{ value: number|Date, label: string }>   ticks across the bottom
 *   yTicks       Array<{ value: number, label: string }>        ticks up the side
 *                                                                (label is what's rendered)
 *   colorScale   'viridis' | 'diverging'   default 'viridis'
 *   zDomain      [min, max]                values are normalised into this
 *                                          (cells outside the range are clamped)
 *   zUnitLabel   string                    e.g. 'SPL (dB)' or 'ΔSPL (dB)'
 *   height       number                    default 320
 *   isLoading    boolean
 *   emptyMessage string
 *   error        string | Error   shows an error overlay (takes precedence over empty/loading)
 */

const MARGIN = { top: 12, right: 80, bottom: 36, left: 56 };

function readCell(source, x, y, cols) {
  if (Array.isArray(source) || ArrayBuffer.isView(source)) {
    return source[y * cols + x];
  }
  return source.valueAt(x, y);
}

function normalize(v, [lo, hi], colorScale) {
  if (!Number.isFinite(v)) return null;
  if (colorScale === "diverging") {
    // Symmetric domain [-mag, +mag]; map to [-1, 1].
    const mag = Math.max(Math.abs(lo), Math.abs(hi));
    if (mag === 0) return 0;
    return Math.max(-1, Math.min(1, v / mag));
  }
  if (hi === lo) return 0;
  return Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
}

export default function FrequencyTimeHeatmap({
  cells,
  cols: colsProp,
  rows: rowsProp,
  xTicks = [],
  yTicks = [],
  // Time-aware layout (optional): when both are supplied the columns and x-axis
  // ticks are positioned on a real time scale spanning xDomain, so the chart
  // follows the selected date range like the line charts. Without them the
  // heatmap falls back to the legacy index-based layout.
  xDomain = null,
  colTimes = null,
  colorScale = "viridis",
  zDomain = [0, 1],
  zUnitLabel = "",
  height = 320,
  isLoading = false,
  emptyMessage = "No data in the selected range.",
  error = null,
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const colorbarRef = useRef(null);
  const captureRef = useRef(null);
  const { width } = useResizeObserver(containerRef);
  const theme = useChartTheme();
  const { offsetMs } = useTimezone();

  const [hover, setHover] = useState(null); // { x, y, value, xLabel, yLabel }

  // Resolve grid dimensions whether `cells` is an array or a generator.
  const { cols, rows, getter, hasData } = useMemo(() => {
    if (!cells) return { cols: 0, rows: 0, getter: null, hasData: false };
    if (Array.isArray(cells) || ArrayBuffer.isView(cells)) {
      const c = colsProp ?? 0;
      const r = rowsProp ?? (c > 0 ? Math.floor(cells.length / c) : 0);
      return {
        cols: c,
        rows: r,
        getter: (x, y) => readCell(cells, x, y, c),
        hasData: c > 0 && r > 0,
      };
    }
    return {
      cols: cells.cols,
      rows: cells.rows,
      getter: (x, y) => cells.valueAt(x, y),
      hasData: cells.cols > 0 && cells.rows > 0,
    };
  }, [cells, colsProp, rowsProp]);

  const innerW = Math.max(0, (width || 0) - MARGIN.left - MARGIN.right);
  const innerH = Math.max(0, height - MARGIN.top - MARGIN.bottom);

  // Time-aware layout. When xDomain + colTimes are valid, columns are placed on
  // a real time scale (px = (t - t0) / (t1 - t0) * innerW) and given a width that
  // reaches the next column. Otherwise we stay on the legacy index layout.
  const timeLayout = useMemo(() => {
    const t0 = xDomain?.[0];
    const t1 = xDomain?.[1];
    const valid =
      Array.isArray(xDomain) &&
      Number.isFinite(t0) &&
      Number.isFinite(t1) &&
      t1 > t0 &&
      Array.isArray(colTimes) &&
      colTimes.length === cols &&
      cols > 0 &&
      innerW > 0;
    if (!valid) return null;

    const scaleX = (t) => ((t - t0) / (t1 - t0)) * innerW;
    const colX = colTimes.map((t) => (Number.isFinite(t) ? scaleX(t) : NaN));

    // Median gap between consecutive columns → fallback width for the last
    // column (and any with a missing neighbour) so cells don't collapse to 0.
    const gaps = [];
    for (let i = 1; i < colX.length; i++) {
      const g = colX[i] - colX[i - 1];
      if (Number.isFinite(g) && g > 0) gaps.push(g);
    }
    gaps.sort((a, b) => a - b);
    const medianStep =
      gaps.length > 0 ? gaps[Math.floor(gaps.length / 2)] : innerW / cols;

    const colW = colX.map((x, i) => {
      const next = i + 1 < colX.length ? colX[i + 1] : NaN;
      const w = Number.isFinite(next) ? next - x : medianStep;
      return Math.max(1, Number.isFinite(w) && w > 0 ? w : medianStep);
    });

    return { t0, t1, scaleX, colX, colW };
  }, [xDomain, colTimes, cols, innerW]);

  // Paint the heatmap. Use canvas so we can scale to DPR without
  // creating cols*rows DOM nodes.
  useEffect(() => {
    if (!hasData || innerW <= 0 || innerH <= 0) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = innerW * dpr;
    canvas.height = innerH * dpr;
    canvas.style.width = `${innerW}px`;
    canvas.style.height = `${innerH}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, innerW, innerH);

    const cellW = innerW / cols;
    const cellH = innerH / rows;
    const colorFn = getColormap(colorScale);

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const v = getter(x, y);
        const t = normalize(v, zDomain, colorScale);
        if (t == null) continue;
        const left = timeLayout ? timeLayout.colX[x] : x * cellW;
        const w = timeLayout ? timeLayout.colW[x] : cellW;
        if (!Number.isFinite(left)) continue;
        ctx.fillStyle = colorFn(t);
        // Slight overlap to avoid faint gaps between cells.
        ctx.fillRect(left, y * cellH, w + 0.5, cellH + 0.5);
      }
    }
  }, [hasData, cols, rows, getter, innerW, innerH, colorScale, zDomain, theme, timeLayout]);

  // Paint the vertical colorbar.
  useEffect(() => {
    const bar = colorbarRef.current;
    if (!bar) return;
    const w = 10;
    const h = innerH;
    const dpr = window.devicePixelRatio || 1;
    bar.width = w * dpr;
    bar.height = h * dpr;
    bar.style.width = `${w}px`;
    bar.style.height = `${h}px`;
    const ctx = bar.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const colorFn = getColormap(colorScale);
    for (let i = 0; i < h; i++) {
      // Top is "high" — t = 1 for viridis, +1 for diverging.
      const t = colorScale === "diverging" ? 1 - (i / h) * 2 : 1 - i / h;
      ctx.fillStyle = colorFn(t);
      ctx.fillRect(0, i, w, 1);
    }
  }, [innerH, colorScale]);

  // Hover detection — work out which cell the pointer is over and surface
  // value + axis labels in the tooltip.
  useEffect(() => {
    if (!hasData) return;
    const el = captureRef.current;
    if (!el) return;
    const handleMove = (event) => {
      const rect = el.getBoundingClientRect();
      const mx = (event.touches?.[0]?.clientX ?? event.clientX) - rect.left;
      const my = (event.touches?.[0]?.clientY ?? event.clientY) - rect.top;
      const cellH = innerH / rows;
      const cy = Math.floor(my / cellH);

      // Resolve the hovered column: by time span when time-aware, else by index.
      let cx;
      if (timeLayout) {
        cx = -1;
        for (let i = 0; i < cols; i++) {
          const l = timeLayout.colX[i];
          if (Number.isFinite(l) && mx >= l && mx < l + timeLayout.colW[i]) {
            cx = i;
            break;
          }
        }
        // Pointer is in an empty stretch (before/after the data) — no tooltip.
        if (cx === -1) {
          setHover(null);
          return;
        }
      } else {
        cx = Math.floor(mx / (innerW / cols));
      }

      if (cx < 0 || cx >= cols || cy < 0 || cy >= rows) {
        setHover(null);
        return;
      }
      const v = getter(cx, cy);
      // Pick nearest x/y tick label for context — cheap O(N) lookup is fine
      // because tick arrays are small (≤ ~10 per axis).
      const yNorm = (cy + 0.5) / rows;
      const xLabel =
        timeLayout && Array.isArray(colTimes) && Number.isFinite(colTimes[cx])
          ? formatTimeTick(colTimes[cx], offsetMs)
          : xTicks.length
            ? xTicks[
                Math.min(
                  xTicks.length - 1,
                  Math.round(((cx + 0.5) / cols) * (xTicks.length - 1)),
                )
              ].label
            : "";
      const yLabel = yTicks.length
        ? yTicks[Math.min(yTicks.length - 1, Math.round(yNorm * (yTicks.length - 1)))].label
        : "";
      const tooltipX = Math.min(
        MARGIN.left + mx + 12,
        (width || 0) - 180,
      );
      const tooltipY = MARGIN.top + my - 8;
      setHover({
        x: tooltipX,
        y: Math.max(MARGIN.top, tooltipY),
        value: v,
        xLabel,
        yLabel,
      });
    };
    const handleLeave = () => setHover(null);
    el.addEventListener("mousemove", handleMove);
    el.addEventListener("mouseleave", handleLeave);
    el.addEventListener("touchmove", handleMove);
    el.addEventListener("touchend", handleLeave);
    return () => {
      el.removeEventListener("mousemove", handleMove);
      el.removeEventListener("mouseleave", handleLeave);
      el.removeEventListener("touchmove", handleMove);
      el.removeEventListener("touchend", handleLeave);
    };
  }, [hasData, innerW, innerH, cols, rows, getter, xTicks, yTicks, width, timeLayout, colTimes, offsetMs]);

  // Tick lines / labels are drawn in SVG so they stay crisp and align
  // with the canvas without us having to manage two coordinate systems
  // imperatively.
  // Time-aware: evenly spaced ticks across the selected range, labelled exactly
  // like the line charts. Legacy: index-spaced ticks sampled from readings.
  const resolvedXTicks = timeLayout
    ? Array.from({ length: X_TICK_COUNT }, (_, i) => {
        const t =
          timeLayout.t0 +
          ((timeLayout.t1 - timeLayout.t0) * i) / (X_TICK_COUNT - 1);
        return { pos: timeLayout.scaleX(t), label: formatTimeTick(t, offsetMs) };
      })
    : xTicks.map((tick, idx) => ({
        pos: (idx / (xTicks.length - 1 || 1)) * innerW,
        label: tick.label,
      }));

  const xTickLabels = resolvedXTicks.length
    ? resolvedXTicks.map((tick, idx) => (
        <text
          key={`xt-${idx}`}
          x={MARGIN.left + tick.pos}
          y={MARGIN.top + innerH + 16}
          textAnchor="middle"
          fontSize={10}
          fill={theme.textSecondary}
        >
          {tick.label}
        </text>
      ))
    : null;

  const yTickLabels = yTicks.length
    ? yTicks.map((tick, idx) => {
        const pos = (idx / (yTicks.length - 1 || 1)) * innerH;
        return (
          <text
            key={`yt-${idx}`}
            x={MARGIN.left - 8}
            y={MARGIN.top + pos + 3}
            textAnchor="end"
            fontSize={10}
            fill={theme.textSecondary}
          >
            {tick.label}
          </text>
        );
      })
    : null;

  // Colorbar tick labels (top = high, bottom = low).
  const colorbarTicks = colorScale === "diverging"
    ? [zDomain[1], (zDomain[1] + zDomain[0]) / 2, zDomain[0]]
    : [zDomain[1], (zDomain[1] + zDomain[0]) / 2, zDomain[0]];

  return (
    <div ref={containerRef} className="relative w-full" style={{ height }}>
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

      {/* Heatmap canvas, absolutely positioned inside the chart area */}
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          left: MARGIN.left,
          top: MARGIN.top,
          pointerEvents: "none",
        }}
      />

      {/* Hover capture (transparent — sits on top of the canvas) */}
      <div
        ref={captureRef}
        style={{
          position: "absolute",
          left: MARGIN.left,
          top: MARGIN.top,
          width: innerW,
          height: innerH,
          cursor: "crosshair",
        }}
      />

      {/* Axis ticks + frame */}
      <svg
        width={width || 0}
        height={height}
        style={{ display: "block", pointerEvents: "none" }}
      >
        {/* Frame */}
        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={innerW}
          height={innerH}
          fill="none"
          stroke={theme.border}
          strokeWidth={1}
        />
        {xTickLabels}
        {yTickLabels}
      </svg>

      {/* Colorbar — positioned on the right margin */}
      <div
        style={{
          position: "absolute",
          right: 12,
          top: MARGIN.top,
          width: 60,
          height: innerH,
          display: innerH > 0 ? "flex" : "none",
          flexDirection: "row",
          alignItems: "stretch",
          gap: 6,
          pointerEvents: "none",
        }}
      >
        <canvas ref={colorbarRef} />
        <div
          className="flex flex-col justify-between"
          style={{ color: theme.textSecondary, fontSize: 10 }}
        >
          {colorbarTicks.map((v, idx) => (
            <span key={`cbt-${idx}`}>
              {Number.isFinite(v) ? (typeof v === "number" ? v.toFixed(0) : String(v)) : ""}
            </span>
          ))}
        </div>
      </div>

      {/* Colorbar unit label, sits just under the colorbar */}
      {zUnitLabel && (
        <div
          className="copy-extrasmall"
          style={{
            position: "absolute",
            right: 12,
            top: MARGIN.top + innerH + 4,
            color: theme.textSecondary,
            textAlign: "right",
            width: 60,
            pointerEvents: "none",
          }}
        >
          {zUnitLabel}
        </div>
      )}

      <ChartTooltip
        open={Boolean(hover)}
        position={{ x: hover?.x ?? 0, y: hover?.y ?? 0 }}
      >
        {hover && (
          <>
            <ChartTooltipTitle>
              {hover.xLabel ? `${hover.xLabel} · ` : ""}
              {hover.yLabel}
            </ChartTooltipTitle>
            <div>
              {Number.isFinite(hover.value) ? hover.value.toFixed(2) : "–"}
              {zUnitLabel ? ` ${zUnitLabel.replace(/^.*\(|\).*$/g, "")}` : ""}
            </div>
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
