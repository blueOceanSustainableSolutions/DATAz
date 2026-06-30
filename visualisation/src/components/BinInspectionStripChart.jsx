"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "@/context/ThemeProvider";

// ─── Constants ───────────────────────────────────────────────────────────────

const CHART_HEIGHT = 180;
const MARGIN       = { top: 14, right: 14, bottom: 28, left: 36 };
const PLOT_HEIGHT  = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;
const X_TICK_COUNT = 5;
const Y_TICKS      = [0, 25, 50, 75, 100];

// ─── Helpers ─────────────────────────────────────────────────────────────────

const pad2 = (n) => String(n).padStart(2, "0");

function fmtTimeFull(ms) {
  const d = new Date(ms);
  return `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}:${pad2(d.getUTCSeconds())}`;
}

function fmtTickShort(ms) {
  const d = new Date(ms);
  return `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
}

function hexToRgb(hex) {
  const h = String(hex || "").replace("#", "");
  const n = parseInt(h.length === 6 ? h : h.replace(/(.)/g, "$1$1"), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

// ─── BinInspectionStripChart ────────────────────────────────────────────────

/**
 * SVG bar chart of all detection events inside a single inspected bin.
 *
 * One bar per event:
 *   - x position  = ingestedAt
 *   - bar height  = intensityPercentage  (clamped to [0, 100])
 *   - fill alpha  = ramps with intensity (faint → opaque)
 *   - stroke      = classColor (or dark accent when selected)
 *
 * Bars with audioUrl are clickable to drive the AcousticViewer above.
 * Hover anywhere over the plot area highlights the nearest bar in x.
 */
export default function BinInspectionStripChart({
  events,
  selectedEvent,
  classColor = "#5F5E5A",
  binStartMs,
  binEndMs,
  onSelectEvent,
}) {
  const { theme } = useTheme();
  const isDark    = theme === "dark";

  const wrapperRef        = useRef(null);
  const [width, setWidth] = useState(0);
  const [hoverIdx, setHover] = useState(null);

  // ── Track wrapper width via ResizeObserver ────────────────────────────────
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── Theme palette ─────────────────────────────────────────────────────────
  const palette = useMemo(() => ({
    grid:       isDark ? "#2e2e2e"      : "rgba(0,0,0,0.07)",
    axis:       isDark ? "#3a3a3a"      : "#cccccc",
    tick:       isDark ? "#6b7f80"      : "#888888",
    tooltipBg:  isDark ? "#1a2428"      : "#ffffff",
    tooltipFg:  isDark ? "#e0ecec"      : "#002121",
    selStroke:  isDark ? "#e0ecec"      : "#002121",
  }), [isDark]);

  const { r, g, b } = useMemo(() => hexToRgb(classColor || "#5F5E5A"), [classColor]);

  // ── Normalise events into plottable points ────────────────────────────────
  const points = useMemo(() => {
    return (events || [])
      .map((ev) => {
        const t = new Date(ev.ingestedAt).getTime();
        if (!Number.isFinite(t)) return null;
        const raw       = Number(ev.intensityPercentage);
        const intensity = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0;
        return { ev, t, intensity };
      })
      .filter(Boolean);
  }, [events]);

  // ── X-axis domain (autosized to actual event spread) ──────────────────────
  const { tMin, tMax } = useMemo(() => {
    if (!points.length) {
      return { tMin: binStartMs || 0, tMax: binEndMs || 0 };
    }
    let lo = points[0].t;
    let hi = points[0].t;
    for (const p of points) {
      if (p.t < lo) lo = p.t;
      if (p.t > hi) hi = p.t;
    }
    if (lo === hi) {
      // Single instant: give 1 min of breathing room either side.
      lo -= 60_000;
      hi += 60_000;
    } else {
      const pad = Math.max((hi - lo) * 0.06, 30_000);
      lo -= pad;
      hi += pad;
    }
    return { tMin: lo, tMax: hi };
  }, [points, binStartMs, binEndMs]);

  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right);

  const xScale = useCallback((t) => {
    if (tMax === tMin) return MARGIN.left + plotWidth / 2;
    return MARGIN.left + ((t - tMin) / (tMax - tMin)) * plotWidth;
  }, [tMin, tMax, plotWidth]);

  const yScale = useCallback((intensity) => (intensity / 100) * PLOT_HEIGHT, []);

  // ── Bar width scales with event density (3px floor, 24px ceiling) ─────────
  const barWidthPx = useMemo(() => {
    if (!plotWidth || !points.length) return 0;
    const slot = plotWidth / points.length;
    return Math.max(3, Math.min(24, slot * 0.6));
  }, [plotWidth, points.length]);

  // ── X-axis tick positions (evenly spaced across domain) ───────────────────
  const xTicks = useMemo(() => {
    if (tMin === tMax) return [tMin];
    return Array.from(
      { length: X_TICK_COUNT },
      (_, i) => tMin + (i / (X_TICK_COUNT - 1)) * (tMax - tMin),
    );
  }, [tMin, tMax]);

  // ── Nearest-bar hover (snap to closest x in plot area) ────────────────────
  const handleMouseMove = useCallback((e) => {
    if (!points.length) return;
    const rect   = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    if (mouseX < MARGIN.left || mouseX > MARGIN.left + plotWidth) {
      setHover(null);
      return;
    }
    let idx       = 0;
    let bestDist  = Infinity;
    for (let i = 0; i < points.length; i++) {
      const dist = Math.abs(xScale(points[i].t) - mouseX);
      if (dist < bestDist) {
        bestDist = dist;
        idx      = i;
      }
    }
    setHover(idx);
  }, [points, plotWidth, xScale]);

  const handleClick = useCallback(() => {
    if (hoverIdx == null) return;
    const p = points[hoverIdx];
    if (!p || !p.ev.audioUrl) return;
    onSelectEvent?.(p.ev);
  }, [hoverIdx, points, onSelectEvent]);

  if (!points.length) return null;

  const hoverPoint = hoverIdx != null ? points[hoverIdx] : null;
  const hoverHasAudio = Boolean(hoverPoint?.ev.audioUrl);

  // ── Tooltip placement (centered on bar, pinned to top of plot) ────────────
  const tooltipLeft = hoverPoint
    ? Math.max(MARGIN.left + 4, Math.min(width - MARGIN.right - 4, xScale(hoverPoint.t)))
    : 0;

  return (
    <div
      ref={wrapperRef}
      className="relative w-full select-none"
      style={{ height: CHART_HEIGHT }}
    >
      {width > 0 && (
        <svg
          width={width}
          height={CHART_HEIGHT}
          className="block"
          style={{ cursor: hoverHasAudio ? "pointer" : "default" }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHover(null)}
          onClick={handleClick}
        >
          {/* Y-axis horizontal grid lines + percentage labels */}
          {Y_TICKS.map((tick) => {
            const y = MARGIN.top + PLOT_HEIGHT - yScale(tick);
            return (
              <g key={`y-${tick}`}>
                <line
                  x1={MARGIN.left}
                  x2={MARGIN.left + plotWidth}
                  y1={y}
                  y2={y}
                  stroke={palette.grid}
                  strokeWidth={1}
                />
                <text
                  x={MARGIN.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fontSize={9}
                  fontFamily="Denim Regular, sans-serif"
                  fill={palette.tick}
                >
                  {tick}%
                </text>
              </g>
            );
          })}

          {/* X-axis baseline */}
          <line
            x1={MARGIN.left}
            x2={MARGIN.left + plotWidth}
            y1={MARGIN.top + PLOT_HEIGHT}
            y2={MARGIN.top + PLOT_HEIGHT}
            stroke={palette.axis}
            strokeWidth={1}
          />

          {/* X-axis ticks + UTC time labels */}
          {xTicks.map((t, idx) => {
            const x = xScale(t);
            return (
              <g key={`x-${idx}`}>
                <line
                  x1={x}
                  x2={x}
                  y1={MARGIN.top + PLOT_HEIGHT}
                  y2={MARGIN.top + PLOT_HEIGHT + 4}
                  stroke={palette.axis}
                  strokeWidth={1}
                />
                <text
                  x={x}
                  y={MARGIN.top + PLOT_HEIGHT + 16}
                  textAnchor="middle"
                  fontSize={9}
                  fontFamily="Denim Regular, sans-serif"
                  fill={palette.tick}
                >
                  {fmtTickShort(t)}
                </text>
              </g>
            );
          })}

          {/* Bars */}
          {points.map((p, idx) => {
            const cx       = xScale(p.t);
            const barH     = yScale(p.intensity);
            const x        = cx - barWidthPx / 2;
            const y        = MARGIN.top + PLOT_HEIGHT - barH;
            const alpha    = 0.35 + (p.intensity / 100) * 0.65;
            const fill     = `rgba(${r},${g},${b},${alpha.toFixed(2)})`;
            const isSel    = selectedEvent && p.ev.ingestedAt === selectedEvent.ingestedAt;
            const isHover  = hoverIdx === idx;
            const stroke   = isSel ? palette.selStroke : classColor;
            const strokeW  = isSel ? 2 : isHover ? 1.5 : 1;

            return (
              <rect
                key={`${p.t}-${idx}`}
                x={x}
                y={y}
                width={barWidthPx}
                height={Math.max(1, barH)}
                fill={fill}
                stroke={stroke}
                strokeWidth={strokeW}
                pointerEvents="none"
              />
            );
          })}
        </svg>
      )}

      {/* Floating tooltip — pinned to top of plot, centered on hovered bar */}
      {hoverPoint && (
        <div
          className="pointer-events-none absolute rounded-[4px] px-8 py-6 text-[10px] shadow-md"
          style={{
            left:           tooltipLeft,
            top:            4,
            transform:      "translateX(-50%)",
            background:     palette.tooltipBg,
            border:         `1px solid ${classColor}`,
            color:          palette.tooltipFg,
            whiteSpace:     "nowrap",
            zIndex:         2,
          }}
        >
          <div>{fmtTimeFull(hoverPoint.t)} UTC</div>
          <div>
            <strong style={{ color: classColor }}>
              {Math.round(hoverPoint.intensity)}%
            </strong>{" "}
            intensity
          </div>
          {hoverPoint.ev.splDb != null && (
            <div>{Number(hoverPoint.ev.splDb).toFixed(1)} dB</div>
          )}
          {hoverHasAudio && (
            <div className="mt-2 italic opacity-70">click to inspect</div>
          )}
        </div>
      )}
    </div>
  );
}
