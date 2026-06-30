"use client";

import clsx from "clsx";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import * as d3 from "d3";
import { useTheme } from "@/context/ThemeProvider";
import {
  getCategoryLabel,
  getCategoryHex,
  getCategoryCell,
  formatBinTooltipRange,
} from "@/lib/detections";

const MARGIN = { top: 10, right: 24, bottom: 32, left: 56 };
const LANE_H = 76;
const LANE_GAP = 1;
const MIN_WIDTH = 420;
const ZOOM_FACTOR_IN = 0.85;
const ZOOM_FACTOR_OUT = 1 / ZOOM_FACTOR_IN;
const MIN_ZOOM_MS = 5 * 60 * 1000;

function EmptyBinToast({ x, y, label, range }) {
  if (x == null || y == null) return null;
  return createPortal(
    <div
      style={{
        position: "fixed",
        left: x,
        top: y,
        transform: "translate(-50%, -100%)",
        zIndex: 9999,
      }}
      className="pointer-events-none w-[min(300px,calc(100vw-32px))] rounded-[8px] border border-grey200 bg-surface px-14 py-12 text-left shadow-[1px_3px_12px_rgba(0,0,0,0.18)] dark:border-grey300 dark:shadow-[1px_3px_16px_rgba(0,0,0,0.45)]"
    >
      <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-textSecondary">
        {label}
      </div>
      <div className="mt-6 text-[12px] text-textPrimary">{range}</div>
      <div className="mt-8 text-[11px] text-textSecondary">
        No detections in this bin
      </div>
    </div>,
    document.body,
  );
}

export default function BinnedAggregatesHeatmap({
  binsPayload,
  rangeStartIso,
  rangeEndIso,
  isFetching,
  categories,
  visibleCategoryKeys,
  onBinClick,
}) {
  const { theme } = useTheme();
  const bins = binsPayload?.bins ?? [];

  const hostRef = useRef(null);
  const svgRef = useRef(null);
  const tipRef = useRef(null);
  const wheelRafRef = useRef(null);

  const [emptyToast, setEmptyToast] = useState(null);

  const rangeStartMs = useMemo(
    () => new Date(rangeStartIso).getTime(),
    [rangeStartIso],
  );
  const rangeEndMs = useMemo(
    () => new Date(rangeEndIso).getTime(),
    [rangeEndIso],
  );

  const [viewStart, setViewStart] = useState(rangeStartMs);
  const [viewEnd, setViewEnd] = useState(rangeEndMs);
  const viewRef = useRef({ start: rangeStartMs, end: rangeEndMs });

  useEffect(() => {
    setViewStart(rangeStartMs);
    setViewEnd(rangeEndMs);
    viewRef.current = { start: rangeStartMs, end: rangeEndMs };
  }, [rangeStartMs, rangeEndMs]);

  const visibleClasses = useMemo(() => {
    const list = categories || [];
    return list.filter((c) => visibleCategoryKeys[c] !== false);
  }, [categories, visibleCategoryKeys]);

  const bgColor = theme === "dark" ? "#1a1a2e" : "#f5f5f7";
  const emptyBinColor = theme === "dark" ? "#2a2a3a" : "#ECECEA";

  const renderD3 = useCallback(() => {
    const host = hostRef.current;
    const svgEl = svgRef.current;
    const tipEl = tipRef.current;
    if (!host || !svgEl || !bins.length || !visibleClasses.length) return;

    const totalW = Math.max(MIN_WIDTH, host.clientWidth || MIN_WIDTH);
    const innerW = totalW - MARGIN.left - MARGIN.right;
    const numLanes = visibleClasses.length;
    const plotH = numLanes * LANE_H + (numLanes - 1) * LANE_GAP;
    const totalH = MARGIN.top + plotH + MARGIN.bottom;

    const svg = d3.select(svgEl);
    svg.attr("width", totalW).attr("height", totalH);

    svg.selectAll("*").remove();

    const vStart = viewRef.current.start;
    const vEnd = viewRef.current.end;

    const xScale = d3
      .scaleTime()
      .domain([new Date(vStart), new Date(vEnd)])
      .range([0, innerW]);

    const clipId = "heatmap-clip-" + Math.random().toString(36).slice(2, 8);
    svg.append("defs")
      .append("clipPath")
      .attr("id", clipId)
      .append("rect")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", innerW)
      .attr("height", plotH);

    const root = svg
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    const g = root.append("g")
      .attr("clip-path", `url(#${clipId})`);

    const colorFns = {};
    visibleClasses.forEach((cls) => {
      const cc = getCategoryHex(cls);
      colorFns[cls] = d3
        .scaleLinear()
        .domain([0, 8, 100])
        .range([bgColor, d3.color(cc).copy({ opacity: 0.18 }).formatRgb(), cc])
        .clamp(true);
    });

    const binMs =
      bins.length > 1
        ? new Date(bins[1].binStart).getTime() -
          new Date(bins[0].binStart).getTime()
        : 60 * 60 * 1000;

    function showTip(ev, cls, bin, cell) {
      if (!tipEl) return;
      const pct = cell ? Number(cell.peakIntensityPercentage) || 0 : 0;
      const count = cell ? Number(cell.events) || 0 : 0;
      const splDb = cell?.peakSplDb;
      const splLabel = splDb != null ? `${Number(splDb).toFixed(1)} dB` : "—";
      const color = getCategoryHex(cls);
      const rangeStr = formatBinTooltipRange(bin.binStart, bin.binEnd || new Date(new Date(bin.binStart).getTime() + binMs).toISOString());

      tipEl.innerHTML = `
        <div style="font-family:var(--font-mono,monospace);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-secondary);margin-bottom:6px">
          ${getCategoryLabel(cls)}
        </div>
        <div style="font-size:13px;color:var(--text-primary);margin-bottom:10px">
          ${rangeStr}
        </div>
        <div style="border-top:1px solid var(--grey-200);padding-top:10px;display:flex;flex-direction:column;gap:6px;font-size:12px">
          <div style="display:flex;justify-content:space-between;gap:10px">
            <span style="color:var(--text-secondary)">Peak intensity</span>
            <span style="font-variant-numeric:tabular-nums;color:var(--text-primary);font-weight:500">${count === 0 ? "—" : Math.round(pct) + "%"}</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:10px">
            <span style="color:var(--text-secondary)">Events</span>
            <span style="font-variant-numeric:tabular-nums;color:var(--text-primary);font-weight:500">${count}</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:10px">
            <span style="color:var(--text-secondary)">Bin peak SPL</span>
            <span style="font-variant-numeric:tabular-nums;color:var(--text-primary);font-weight:500">${splLabel}</span>
          </div>
        </div>`;

      const hostRect = host.getBoundingClientRect();
      const mx = ev.clientX - hostRect.left;
      const tipW = tipEl.offsetWidth || 200;
      let px = mx + 14;
      if (px + tipW > hostRect.width - 8) px = mx - tipW - 14;
      tipEl.style.left = px + "px";
      tipEl.style.top = MARGIN.top - 2 + "px";
      tipEl.style.opacity = "1";
    }

    function hideTip() {
      if (!tipEl) return;
      tipEl.style.opacity = "0";
    }

    // Crosshair line spanning all lanes (unclipped so it spans full height)
    const crosshair = root
      .append("line")
      .attr("y1", 0)
      .attr("y2", plotH)
      .attr("stroke", "var(--text-primary)")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2 3")
      .attr("opacity", 0)
      .attr("pointer-events", "none");

    // Lanes
    visibleClasses.forEach((cls, idx) => {
      const yOff = idx * (LANE_H + LANE_GAP);
      const lane = g.append("g").attr("transform", `translate(0,${yOff})`);

      lane
        .append("rect")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", innerW)
        .attr("height", LANE_H)
        .attr("fill", "var(--grey-100)")
        .attr("rx", 0);

      // Rotated y-axis label (rendered outside clip path)
      const labelCx = MARGIN.left - 26;
      const labelCy = MARGIN.top + yOff + LANE_H / 2;
      svg
        .append("text")
        .attr("x", labelCx)
        .attr("y", labelCy)
        .attr("text-anchor", "middle")
        .attr("transform", `rotate(-90 ${labelCx} ${labelCy})`)
        .style("font-size", "12px")
        .style("font-weight", "500")
        .style("letter-spacing", "0.06em")
        .style("text-transform", "uppercase")
        .style("fill", "var(--text-secondary)")
        .style("font-family", "inherit")
        .text(getCategoryLabel(cls));

      // Cells
      const cellData = bins.map((bin) => {
        const cell = getCategoryCell(bin, cls);
        const pct = cell ? Number(cell.peakIntensityPercentage) || 0 : 0;
        const count = cell ? Number(cell.events) || 0 : 0;
        return { bin, cell, pct, count, t: new Date(bin.binStart).getTime() };
      });

      lane
        .append("g")
        .selectAll("rect.cell")
        .data(cellData)
        .join("rect")
        .attr("class", "cell")
        .attr("x", (d) => xScale(new Date(d.t)))
        .attr("y", 1)
        .attr("width", (d) =>
          Math.max(
            1,
            xScale(new Date(d.t + binMs)) - xScale(new Date(d.t)) - 1,
          ),
        )
        .attr("height", LANE_H - 2)
        .attr("fill", (d) =>
          d.count === 0 ? emptyBinColor : colorFns[cls](d.pct),
        )
        .attr("stroke", "transparent")
        .attr("stroke-width", 1)
        .style("cursor", "pointer")
        .on("mouseenter", function (ev, d) {
          d3.select(this).attr("stroke", "var(--text-primary)").attr("stroke-opacity", 0.5);
          showTip(ev, cls, d.bin, d.cell);
          crosshair
            .attr(
              "x1",
              xScale(new Date(d.t)) +
                (xScale(new Date(d.t + binMs)) - xScale(new Date(d.t))) / 2,
            )
            .attr(
              "x2",
              xScale(new Date(d.t)) +
                (xScale(new Date(d.t + binMs)) - xScale(new Date(d.t))) / 2,
            )
            .attr("opacity", 0.65);
        })
        .on("mousemove", function (ev, d) {
          showTip(ev, cls, d.bin, d.cell);
        })
        .on("mouseleave", function () {
          d3.select(this).attr("stroke", "transparent");
          hideTip();
          crosshair.attr("opacity", 0);
        })
        .on("click", function (ev, d) {
          const eventCount = d.count;
          if (eventCount === 0) {
            setEmptyToast({
              x: ev.clientX,
              y: ev.clientY - 12,
              label: getCategoryLabel(cls),
              range: formatBinTooltipRange(
                d.bin.binStart,
                d.bin.binEnd,
              ),
            });
            setTimeout(() => setEmptyToast(null), 2500);
            return;
          }
          onBinClick?.({
            classId: cls,
            binStart: d.bin.binStart,
            binEnd: d.bin.binEnd,
            events: eventCount,
          });
        });
    });

    // X-axis — smart tick format based on view duration
    const viewDurMs = vEnd - vStart;
    const viewDurH = viewDurMs / 3_600_000;
    let tickFmt;
    if (viewDurH <= 24) {
      tickFmt = d3.timeFormat("%H:%M");
    } else if (viewDurH <= 120) {
      tickFmt = d3.timeFormat("%b %d, %H:%M");
    } else {
      tickFmt = d3.timeFormat("%b %d");
    }

    const xAxis = d3
      .axisBottom(xScale)
      .ticks(Math.min(8, Math.floor(innerW / 100)))
      .tickFormat(tickFmt)
      .tickSizeOuter(0);

    root.append("g")
      .attr("transform", `translate(0,${plotH + 2})`)
      .call(xAxis)
      .call((sel) => sel.select(".domain").remove())
      .call((sel) =>
        sel.selectAll("line").attr("stroke", "var(--grey-200)"),
      )
      .call((sel) =>
        sel
          .selectAll("text")
          .style("font-size", "12px")
          .style("fill", "var(--text-secondary)")
          .style("font-family", "inherit"),
      );

    // Double-click to reset zoom
    svg.on("dblclick", () => {
      viewRef.current = { start: rangeStartMs, end: rangeEndMs };
      setViewStart(rangeStartMs);
      setViewEnd(rangeEndMs);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    bins,
    visibleClasses,
    bgColor,
    rangeStartMs,
    rangeEndMs,
    onBinClick,
    // viewStart/viewEnd are render triggers — the callback reads viewRef.current
    viewStart,
    viewEnd,
  ]);

  // Render D3 on data / view / theme changes
  useEffect(() => {
    renderD3();
  }, [renderD3, theme]);

  // Scroll-wheel zoom. The empty-bins branch returns a plain <div>, so the
  // SVG ref isn't populated until bins arrive — re-bind when that flips.
  const hasBins = bins.length > 0;
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const handler = (ev) => {
      ev.preventDefault();
      const rect = svgEl.getBoundingClientRect();
      const totalW = svgEl.clientWidth || rect.width;
      const innerW = totalW - MARGIN.left - MARGIN.right;
      const scaleX = totalW / rect.width;
      const localX = (ev.clientX - rect.left) * scaleX - MARGIN.left;
      const clampedX = Math.max(0, Math.min(innerW, localX));

      const vStart = viewRef.current.start;
      const vEnd = viewRef.current.end;
      const curDur = vEnd - vStart;

      const xScale = d3
        .scaleTime()
        .domain([new Date(vStart), new Date(vEnd)])
        .range([0, innerW]);
      const anchorT = xScale.invert(clampedX).getTime();

      const factor = ev.deltaY < 0 ? ZOOM_FACTOR_IN : ZOOM_FACTOR_OUT;
      let newDur = curDur * factor;
      const maxDur = rangeEndMs - rangeStartMs;
      newDur = Math.max(MIN_ZOOM_MS, Math.min(maxDur, newDur));
      if (newDur === curDur) return;

      const anchorRatio = clampedX / innerW;
      let newStart = anchorT - anchorRatio * newDur;
      let newEnd = newStart + newDur;
      if (newStart < rangeStartMs) {
        newStart = rangeStartMs;
        newEnd = newStart + newDur;
      }
      if (newEnd > rangeEndMs) {
        newEnd = rangeEndMs;
        newStart = newEnd - newDur;
      }

      viewRef.current = {
        start: Math.round(newStart),
        end: Math.round(newEnd),
      };

      if (!wheelRafRef.current) {
        wheelRafRef.current = requestAnimationFrame(() => {
          wheelRafRef.current = null;
          setViewStart(viewRef.current.start);
          setViewEnd(viewRef.current.end);
        });
      }
    };

    svgEl.addEventListener("wheel", handler, { passive: false });
    return () => svgEl.removeEventListener("wheel", handler);
  }, [rangeStartMs, rangeEndMs, hasBins]);

  // ResizeObserver
  useEffect(() => {
    const el = hostRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => renderD3());
    ro.observe(el);
    return () => ro.disconnect();
  }, [renderD3]);

  if (!bins.length) {
    return (
      <div className="flex h-[220px] items-center justify-center px-24 text-[14px] text-textSecondary">
        No bins in this range.
      </div>
    );
  }

  if (!visibleClasses.length && bins.length > 0) {
    return (
      <div className="flex h-[220px] items-center justify-center px-24 text-center text-[12px] leading-[150%] text-textSecondary">
        All classes hidden — click a legend item to show
      </div>
    );
  }

  return (
    <div
      ref={hostRef}
      className={clsx(
        "relative px-8 pt-6 pb-8 transition-opacity duration-300 ease-out 768:px-[18px]",
        isFetching && "opacity-[0.88]",
      )}
      style={{ minWidth: MIN_WIDTH }}
    >
      <svg
        ref={svgRef}
        style={{
          display: "block",
          width: "100%",
          cursor: "crosshair",
          fontFamily: "inherit",
        }}
      />
      {/* Inline tooltip */}
      <div
        ref={tipRef}
        className="pointer-events-none absolute rounded-[8px] border border-grey200 bg-surface shadow-[0_4px_16px_rgba(0,0,0,0.10)] dark:border-grey300 dark:shadow-[0_4px_16px_rgba(0,0,0,0.4)]"
        style={{
          opacity: 0,
          transition: "opacity 0.12s",
          zIndex: 20,
          padding: "12px 14px",
          fontSize: "12px",
          minWidth: 210,
          whiteSpace: "nowrap",
          fontFamily: "var(--font-mono, monospace)",
        }}
      />
      {/* Empty-bin toast — positional, auto-dismissing */}
      {emptyToast?.x != null && (
        <EmptyBinToast
          x={emptyToast.x}
          y={emptyToast.y}
          label={emptyToast.label}
          range={emptyToast.range}
        />
      )}
    </div>
  );
}
