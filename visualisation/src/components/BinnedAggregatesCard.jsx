"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { fetchDetectionsBins } from "@/api/detections-overview";
import { useSiteDetectionsBins } from "@/hooks/useSiteDetectionsBins";
import {
  getCategoryColor,
  getCategoryHex,
  getCategoryLabel,
  buildGlobalCategoryOrder,
  formatBinWidthLabel,
  getAdaptiveBinMinutes,
  getCategoryCell,
  rankCategory,
} from "@/lib/detections";
import { foldBinsSeries } from "@/lib/siteDetections";
import BinnedAggregatesHeatmap from "@/components/BinnedAggregatesHeatmap";

/** Categories always shown as rows even when no events exist in the range.
 *  Must match the exact category string stored in the DB classes table (singular). */
const PINNED_CATEGORIES = ["vessel", "dolphin"];

// ─── Absorbed sub-components ────────────────────────────────────────────────

/**
 * Manual bin options — only values strictly coarser than Auto are offered,
 * so every manual choice aggregates more detections per bin than the default.
 */
const ALL_MANUAL = [
  { id: "5",     label: "5m",  minutes: 5 },
  { id: "15",    label: "15m", minutes: 15 },
  { id: "30",    label: "30m", minutes: 30 },
  { id: "60",    label: "1h",  minutes: 60 },
  { id: "180",   label: "3h",  minutes: 180 },
  { id: "360",   label: "6h",  minutes: 360 },
  { id: "720",   label: "12h", minutes: 720 },
  { id: "1440",  label: "1d",  minutes: 1440 },
  { id: "4320",  label: "3d",  minutes: 4320 },
  { id: "10080", label: "1w",  minutes: 10080 },
];

function buildOptions(rangeHours) {
  const rh = Number.isFinite(rangeHours) ? rangeHours : 24;
  const autoMin = getAdaptiveBinMinutes(0, rh * 3_600_000);

  const coarser = ALL_MANUAL.filter((o) => o.minutes > autoMin);
  const capped = coarser.slice(0, 3);
  return [{ id: "auto", label: "Auto", minutes: null }, ...capped];
}

/**
 * Segmented bin-mode picker.
 */
function BinnedBinModeControls({
  mode,
  onModeChange,
  intervalMinutes = 1,
  rangeHours = 24,
  isHtsDevice = false,
  onReset,
}) {
  const min     = Math.max(1, Number(intervalMinutes) || 1);
  const options = buildOptions(rangeHours, isHtsDevice);

  const isActive = (opt) => {
    if (opt.id === "auto") return mode === "auto";
    return mode === opt.minutes;
  };

  return (
    <div className="inline-flex items-center gap-8">
      <div
        className={clsx(
          "inline-flex rounded-[7px] border p-[2px]",
          "border-grey300 bg-surface",
          "dark:border-grey200",
        )}
      >
        {options.map((opt) => {
          const disabled = opt.minutes != null && opt.minutes < min;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={disabled}
              onClick={() => {
                if (opt.id === "auto") onModeChange("auto");
                else if (!disabled)
                  onModeChange(Math.max(opt.minutes, min));
              }}
              className={clsx(
                "rounded-[5px] border-none bg-transparent px-10 py-5 font-mono text-[12px] font-medium uppercase tracking-[0.04em] transition-all duration-150",
                disabled && "cursor-not-allowed opacity-40",
                !disabled &&
                  (isActive(opt)
                    ? "bg-primarySelected text-primary"
                    : "text-textSecondary hover:text-textPrimary"),
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        className={clsx(
          "flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-[6px] border",
          "border-grey300 bg-surface text-textSecondary",
          "transition-all duration-150 hover:bg-grey100 hover:text-textPrimary",
          "dark:border-grey200",
        )}
        title="Reset zoom"
        aria-label="Reset zoom"
        onClick={onReset}
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden
        >
          <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
          <path d="M21 3v5h-5" />
        </svg>
      </button>
    </div>
  );
}

/**
 * Template: .legend / .legend-item / .legend-swatch — heatmap class toggles.
 */
function BinnedHeatmapLegend({ items, hiddenKeys, onToggle }) {
  if (!items?.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-12 font-mono text-[11px] text-textPrimary">
      {items.map((item) => {
        const hidden = hiddenKeys[item.key];
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onToggle(item.key)}
            className={clsx(
              "flex cursor-pointer select-none items-center gap-6 rounded-[6px] px-8 py-3 transition-[opacity,background] duration-150",
              "hover:bg-grey200 dark:hover:bg-grey300/40",
              hidden && "opacity-40 line-through decoration-textSecondary decoration-1",
            )}
          >
            <span
              className={clsx(
                "h-10 w-10 shrink-0 rounded-[2px]",
                hidden && "grayscale-[0.7]",
              )}
              style={{ backgroundColor: item.color }}
              aria-hidden
            />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Template: .interaction-hint / .hint-key — AI_Detections_Visualisation.html
 */
function BinnedAggregatesInteractionHint() {
  return (
    <div className="flex flex-nowrap justify-between gap-x-8 border-t border-grey200 bg-grey100 px-12 py-10 font-mono text-[10px] tracking-[0.04em] text-textSecondary 768:flex-wrap 768:justify-start 768:gap-x-20 768:gap-y-10 768:px-20 768:py-11 768:text-[11px] dark:border-grey300">
      <span className="inline-flex items-center whitespace-nowrap">
        <span className="mr-6 inline-block rounded-[3px] border border-grey300 bg-surface px-6 py-2 font-mono text-[10px] font-medium text-textPrimary dark:border-grey400">
          CLICK
        </span>
        <span className="hidden 768:inline">cell to inspect</span>
      </span>
      <span className="inline-flex items-center whitespace-nowrap">
        <span className="mr-6 inline-block rounded-[3px] border border-grey300 bg-surface px-6 py-2 font-mono text-[10px] font-medium text-textPrimary dark:border-grey400">
          SCROLL
        </span>
        <span className="hidden 768:inline">to zoom</span>
      </span>
      <span className="inline-flex items-center whitespace-nowrap">
        <span className="mr-6 inline-block rounded-[3px] border border-grey300 bg-surface px-6 py-2 font-mono text-[10px] font-medium text-textPrimary dark:border-grey400">
          DBL-CLICK
        </span>
        <span className="hidden 768:inline">reset</span>
      </span>
    </div>
  );
}

/**
 * AI_Detections_Visualisation.html — Binned aggregates card:
 * chart-header → chart-toolbar (density + legend) → #heatmap 260px → interaction-hint.
 */
export default function BinnedAggregatesCard({
  scoutId,
  startIso,
  endIso,
  authToken,
  overviewIntervalMinutes,
  onOpenBinInspection,
  // Site (multi-deployment) mode: when provided, fetches via the Site bulk
  // endpoint and folds the per-htId series into a single combined heatmap.
  siteContext,
}) {
  const isMulti = Boolean(siteContext);
  const isHtsDevice = !isMulti && Boolean(scoutId?.toLowerCase().includes('-s-'));
  /** 'auto' | 5 | 15 | 60 — mirrors template data-bin + Auto */
  const [binMode, setBinMode] = useState("auto");
  const [visibleCat, setVisibleCat] = useState({});

  /** Floor from deployment/overview (parent passes data?.intervalMinutes when loaded). */
  const intervalFloor = Math.max(
    1,
    Number(overviewIntervalMinutes) || 1,
  );

  const rangeHours = useMemo(() => {
    const start = new Date(startIso).getTime();
    const end   = new Date(endIso).getTime();
    if (!Number.isFinite(start) || !Number.isFinite(end)) return 24;
    return (end - start) / 3_600_000;
  }, [startIso, endIso]);

  const requestedBinMinutes = useMemo(() => {
    const start = new Date(startIso).getTime();
    const end = new Date(endIso).getTime();
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      return Math.max(15, intervalFloor);
    }
    if (binMode === "auto") {
      return Math.max(getAdaptiveBinMinutes(start, end), intervalFloor);
    }
    return Math.max(Number(binMode), intervalFloor);
  }, [binMode, startIso, endIso, intervalFloor]);

  // Scout data source — single hydrotwin.
  const scoutQuery = useQuery({
    queryKey: [
      "detectionsBins",
      scoutId,
      startIso,
      endIso,
      requestedBinMinutes,
    ],
    queryFn: ({ signal }) =>
      fetchDetectionsBins(
        scoutId,
        startIso,
        endIso,
        requestedBinMinutes,
        authToken,
        signal,
      ),
    enabled: !isMulti && Boolean(scoutId && authToken && startIso && endIso),
    placeholderData: (previousData) => previousData,
  });

  // Site data source — bulk fan-out + client-side fold.
  const siteQuery = useSiteDetectionsBins(
    isMulti ? siteContext.siteId : null,
    isMulti ? siteContext.htIds : [],
    startIso,
    endIso,
    requestedBinMinutes,
  );
  const foldedSiteBins = useMemo(
    () => (isMulti ? foldBinsSeries(siteQuery.series) : null),
    [isMulti, siteQuery.series],
  );

  const data = isMulti ? foldedSiteBins : scoutQuery.data;
  const isLoading = isMulti ? siteQuery.isLoading : scoutQuery.isLoading;
  const isFetching = isMulti ? siteQuery.isLoading : scoutQuery.isFetching;
  const error = isMulti ? siteQuery.error : scoutQuery.error;

  const intervalMinResolved =
    data?.intervalMinutes ?? overviewIntervalMinutes ?? 1;

  const effectiveBinMinutes =
    data?.binMinutes != null ? data.binMinutes : requestedBinMinutes;

  const categories = useMemo(() => {
    const fromData = buildGlobalCategoryOrder(data?.bins ?? []);
    // Ensure pinned categories always appear as rows, ordered by rank when inserted.
    const merged = [...fromData];
    for (const def of PINNED_CATEGORIES) {
      if (!merged.includes(def)) {
        const defRank = rankCategory(def);
        const insertIdx = merged.findIndex((c) => rankCategory(c) > defRank);
        if (insertIdx === -1) merged.push(def);
        else merged.splice(insertIdx, 0, def);
      }
    }
    return merged;
  }, [data?.bins]);

  useEffect(() => {
    setVisibleCat((prev) => {
      const next = { ...prev };
      for (const c of categories) {
        if (!(c in next)) next[c] = true;
      }
      return next;
    });
  }, [categories]);

  const legendItems = useMemo(
    () =>
      categories.map((c) => ({
        key: c,
        label: getCategoryLabel(c),
        color: getCategoryColor(c),
      })),
    [categories],
  );

  const legendHidden = useMemo(() => {
    const o = {};
    for (const c of categories) {
      if (visibleCat[c] === false) o[c] = true;
    }
    return o;
  }, [categories, visibleCat]);

  const toggleLegend = (key) => {
    setVisibleCat((prev) => {
      const vis = prev[key] !== false;
      return { ...prev, [key]: vis ? false : true };
    });
  };

  const densityBinLabel = formatBinWidthLabel(effectiveBinMinutes);
  const rawIntervalLabel = `${intervalMinResolved}min`;

  // Build navigation list for modal: bins of the same class that have events
  const handleBinClick = useCallback(
    ({ classId, binStart, binEnd }) => {
      if (!onOpenBinInspection) return;
      const allBins = data?.bins ?? [];
      const binsForNavigation = allBins
        .filter((bin) => {
          const cell = getCategoryCell(bin, classId);
          return cell && (Number(cell.events) || 0) > 0;
        })
        .map((bin) => ({ binStart: bin.binStart, binEnd: bin.binEnd }));

      onOpenBinInspection({
        classId,
        className: getCategoryLabel(classId),
        classColor: getCategoryHex(classId),
        binStart,
        binEnd,
        binMinutes: effectiveBinMinutes,
        binsForNavigation,
        focused: false,
        pinnedEventAt: null,
      });
    },
    [onOpenBinInspection, data, effectiveBinMinutes],
  );

  if (!isMulti && !authToken) {
    return null;
  }

  if (isLoading && !data) {
    return (
      <div className="border-b border-grey200">
        <div className="flex items-center gap-16 border-b border-grey200 bg-grey100 px-20 pt-14 pb-12">
          <span className="copy-body font-semibold leading-tight text-textPrimary">
            Detection Timeline
          </span>
        </div>
        <div className="px-20 py-28 font-mono text-[14px] text-textSecondary">
          Loading bins…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-b border-grey200 p-20 font-mono text-[14px] text-error">
        {error.message || "Could not load binned aggregates."}
      </div>
    );
  }

  return (
    <div className="border-b border-grey200">
      {/* headers (title/controls + density/legend) */}
      <div className="border-b border-grey200 dark:border-grey300">
        <div className="flex flex-row items-center justify-between gap-12 bg-grey100 px-20 pt-14 pb-12 640:gap-16">
          <span className="copy-body flex-shrink-0 font-semibold leading-tight text-textPrimary">
            Detection Timeline
          </span>

          <div className="flex min-w-0 overflow-x-auto" style={{ scrollbarWidth: "thin" }}>
            <BinnedBinModeControls
              mode={binMode === "auto" ? "auto" : Number(binMode)}
              onModeChange={(m) => setBinMode(m === "auto" ? "auto" : m)}
              intervalMinutes={intervalMinResolved}
              rangeHours={rangeHours}
              isHtsDevice={isHtsDevice}
              onReset={() => setBinMode("auto")}
            />
          </div>
        </div>

        <div className="flex flex-col gap-12 border-t border-grey200 bg-grey100 px-20 py-10 640:flex-row 640:items-center 640:justify-between 640:gap-16 dark:border-grey300">
          <div className="flex min-w-0 items-center gap-8 font-mono text-[11px] tracking-[0.04em] text-textSecondary">
            <span
              className="h-[5px] w-[5px] shrink-0 rounded-full bg-textSecondary opacity-60"
              aria-hidden
            />
            <span className="truncate">
              Showing{" "}
              <strong className="font-medium text-textPrimary">
                {densityBinLabel}
              </strong>{" "}
              bins · raw interval{" "}
              <strong className="font-medium text-textPrimary">
                {rawIntervalLabel}
              </strong>
            </span>
          </div>
          <BinnedHeatmapLegend
            items={legendItems}
            hiddenKeys={legendHidden}
            onToggle={toggleLegend}
          />
        </div>
      </div>

      {/* overflow-x-auto lets the full-width heatmap scroll horizontally on
          mobile (host enforces a min-width) instead of overflowing the card. */}
      <div className="overflow-x-auto" style={{ scrollbarWidth: "thin" }}>
        <BinnedAggregatesHeatmap
          binsPayload={data}
          rangeStartIso={startIso}
          rangeEndIso={endIso}
          isFetching={Boolean(isFetching && data)}
          categories={categories}
          visibleCategoryKeys={visibleCat}
          onBinClick={onOpenBinInspection ? handleBinClick : undefined}
        />
      </div>

      <BinnedAggregatesInteractionHint />
    </div>
  );
}
