"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { useTheme } from "@/context/ThemeProvider";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";

// ─── Constants ───────────────────────────────────────────────────────────────

const CHART_HEIGHT = 240;
const MARGIN = { top: 18, right: 14, bottom: 28, left: 36 };
const PLOT_HEIGHT = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;
const X_TICK_COUNT = 5;
const Y_TICKS = [0, 25, 50, 75, 100];
const DOT_RADIUS = 5;
const COLLIDE_RADIUS = DOT_RADIUS + 1;
const SIM_TICKS = 120;

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

// ─── BinInspectionBeeswarmChart ─────────────────────────────────────────────

/**
 * D3 beeswarm of detection events inside a single inspected bin, used on the
 * Site (multi-deployment) page in place of BinInspectionStripChart.
 *
 *   x = ingestedAt (time within the bin)
 *   y = intensityPercentage (0–100)
 *   colour = deployment, via getOverlayColor({ htId, scopedHydrotwins })
 *   shape  = solid filled circle for HT-C, hollow + dashed stroke for HT-S
 *
 * d3-force resolves overlaps so coincident events never hide each other.
 * Dots from deployments not matching `depFilter` (when set) fade to 0.15
 * opacity — preserving layout but visually isolating one deployment.
 */
export default function BinInspectionBeeswarmChart({
  events,
  selectedEvent,
  scopedHydrotwins,
  depFilter,
  binStartMs,
  binEndMs,
  onSelectEvent,
}) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const wrapperRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [hoverNodeIdx, setHoverNodeIdx] = useState(null);

  // ── Track wrapper width via ResizeObserver ──────────────────────────────────
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── Theme palette ───────────────────────────────────────────────────────────
  const palette = useMemo(
    () => ({
      grid: isDark ? "#2e2e2e" : "rgba(0,0,0,0.07)",
      axis: isDark ? "#3a3a3a" : "#cccccc",
      tick: isDark ? "#6b7f80" : "#888888",
      tooltipBg: isDark ? "#1a2428" : "#ffffff",
      tooltipFg: isDark ? "#e0ecec" : "#002121",
      tooltipBorder: isDark ? "#2a3f44" : "rgba(0,0,0,0.10)",
    }),
    [isDark],
  );

  // ── Scales ──────────────────────────────────────────────────────────────────
  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right);

  const xScale = useMemo(() => {
    if (!plotWidth || !Number.isFinite(binStartMs) || !Number.isFinite(binEndMs)) {
      return null;
    }
    return d3
      .scaleTime()
      .domain([new Date(binStartMs), new Date(binEndMs)])
      .range([0, plotWidth]);
  }, [plotWidth, binStartMs, binEndMs]);

  const yScale = useMemo(
    () => d3.scaleLinear().domain([0, 100]).range([PLOT_HEIGHT, 0]),
    [],
  );

  // ── Simulation: lock to (x, y) target with collision resolution ─────────────
  // `nodes` keeps the original event reference alongside the resolved (x, y)
  // pixel coordinates. Re-runs whenever the inputs that shift positions change.
  const nodes = useMemo(() => {
    if (!xScale) return [];

    const init = events.map((ev, idx) => {
      const tMs = new Date(ev.ingestedAt).getTime();
      const xTarget = xScale(new Date(tMs));
      const yTarget = yScale(Math.min(100, Math.max(0, Number(ev.intensityPercentage) || 0)));
      return {
        idx,
        ev,
        xTarget,
        yTarget,
        x: xTarget,
        y: yTarget,
      };
    });

    if (init.length === 0) return [];

    const sim = d3
      .forceSimulation(init)
      .force("x", d3.forceX((d) => d.xTarget).strength(0.9))
      .force("y", d3.forceY((d) => d.yTarget).strength(0.35))
      .force("collide", d3.forceCollide(COLLIDE_RADIUS).iterations(2))
      .stop();

    for (let i = 0; i < SIM_TICKS; i++) sim.tick();

    // Clamp into the plot region after the simulation.
    for (const n of init) {
      n.x = Math.max(0, Math.min(plotWidth, n.x));
      n.y = Math.max(0, Math.min(PLOT_HEIGHT, n.y));
    }

    return init;
  }, [events, xScale, yScale, plotWidth]);

  // ── Hover-derived tooltip text ──────────────────────────────────────────────
  const hoverNode =
    hoverNodeIdx != null
      ? nodes.find((n) => n.idx === hoverNodeIdx)
      : null;

  // ── X/Y axis tick generation ────────────────────────────────────────────────
  const xTicks = useMemo(() => {
    if (!xScale) return [];
    return xScale.ticks(X_TICK_COUNT);
  }, [xScale]);

  if (!plotWidth) {
    return (
      <div
        ref={wrapperRef}
        className="relative w-full"
        style={{ height: CHART_HEIGHT }}
      />
    );
  }

  const selectedIngestedAt = selectedEvent?.ingestedAt ?? null;

  return (
    <div ref={wrapperRef} className="relative w-full" style={{ height: CHART_HEIGHT }}>
      <svg
        width={width}
        height={CHART_HEIGHT}
        role="img"
        aria-label="Detection beeswarm"
      >
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {/* Y grid lines */}
          {Y_TICKS.map((t) => (
            <line
              key={`y-grid-${t}`}
              x1={0}
              x2={plotWidth}
              y1={yScale(t)}
              y2={yScale(t)}
              stroke={palette.grid}
              strokeWidth={0.5}
            />
          ))}

          {/* Y axis line */}
          <line
            x1={0}
            x2={0}
            y1={0}
            y2={PLOT_HEIGHT}
            stroke={palette.axis}
            strokeWidth={0.5}
          />

          {/* Y ticks/labels */}
          {Y_TICKS.map((t) => (
            <g key={`y-tick-${t}`} transform={`translate(0,${yScale(t)})`}>
              <line x1={-4} x2={0} stroke={palette.axis} strokeWidth={0.5} />
              <text
                x={-8}
                y={3}
                textAnchor="end"
                fontSize={10}
                fill={palette.tick}
                fontFamily="ui-monospace, SFMono-Regular, monospace"
              >
                {t}%
              </text>
            </g>
          ))}

          {/* X axis */}
          <line
            x1={0}
            x2={plotWidth}
            y1={PLOT_HEIGHT}
            y2={PLOT_HEIGHT}
            stroke={palette.axis}
            strokeWidth={0.5}
          />
          {xTicks.map((tick) => (
            <g
              key={`x-tick-${tick.getTime()}`}
              transform={`translate(${xScale(tick)},${PLOT_HEIGHT})`}
            >
              <line y1={0} y2={4} stroke={palette.axis} strokeWidth={0.5} />
              <text
                y={16}
                textAnchor="middle"
                fontSize={10}
                fill={palette.tick}
                fontFamily="ui-monospace, SFMono-Regular, monospace"
              >
                {fmtTickShort(tick.getTime())}
              </text>
            </g>
          ))}

          {/* Hover capture rect — sits below dots so dot hover handlers win */}
          <rect
            x={0}
            y={0}
            width={plotWidth}
            height={PLOT_HEIGHT}
            fill="transparent"
            onMouseLeave={() => setHoverNodeIdx(null)}
          />

          {/* Dots — every detection renders as a solid filled circle coloured
              by deployment; selection/hover are signalled by a subtle stroke,
              not by changing the fill style. */}
          {nodes.map((n) => {
            const ev = n.ev;
            const htId = ev.htId ?? null;
            const color = htId && scopedHydrotwins
              ? getOverlayColor({ htId, scopedHydrotwins })
              : palette.tick;

            const isFiltered =
              depFilter != null && htId !== depFilter;
            const isSelected =
              selectedIngestedAt &&
              ev.ingestedAt === selectedIngestedAt &&
              ev.htId === selectedEvent?.htId;
            const isHover = hoverNodeIdx === n.idx;

            const opacity = isFiltered ? 0.15 : 1;
            const radius = isSelected ? DOT_RADIUS + 1.2 : DOT_RADIUS;
            const stroke = isSelected
              ? palette.tooltipFg
              : isHover
                ? color
                : "transparent";
            const strokeWidth = isSelected ? 2 : isHover ? 1.5 : 0;

            return (
              <circle
                key={`dot-${n.idx}`}
                cx={n.x}
                cy={n.y}
                r={radius}
                fill={color}
                stroke={stroke}
                strokeWidth={strokeWidth}
                opacity={opacity}
                style={{ cursor: ev.audioUrl ? "pointer" : "default" }}
                onMouseEnter={() => setHoverNodeIdx(n.idx)}
                onMouseLeave={() => setHoverNodeIdx(null)}
                onClick={() => {
                  if (!ev.audioUrl) return;
                  onSelectEvent?.(ev);
                }}
              />
            );
          })}
        </g>
      </svg>

      {/* Tooltip */}
      {hoverNode && (
        <div
          className="pointer-events-none absolute z-10 rounded-[6px] border px-10 py-6 font-mono text-[11px] shadow-[0_4px_12px_rgba(0,0,0,0.18)]"
          style={{
            left: Math.min(
              width - 200,
              Math.max(0, MARGIN.left + hoverNode.x - 100),
            ),
            top: Math.max(0, MARGIN.top + hoverNode.y - 70),
            background: palette.tooltipBg,
            color: palette.tooltipFg,
            borderColor: palette.tooltipBorder,
          }}
        >
          <div className="font-medium">
            {hoverNode.ev.htId ?? "—"}
          </div>
          <div className="text-[10px] opacity-75">
            {fmtTimeFull(new Date(hoverNode.ev.ingestedAt).getTime())} UTC
          </div>
          <div className="mt-2">
            <span className="font-medium">
              {Math.round(Number(hoverNode.ev.intensityPercentage) || 0)}%
            </span>
            {hoverNode.ev.splDb != null && (
              <> · {Number(hoverNode.ev.splDb).toFixed(1)} dB</>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
