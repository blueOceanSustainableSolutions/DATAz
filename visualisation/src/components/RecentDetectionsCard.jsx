"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { fetchRecentDetections } from "@/api/detections-overview";
import { useSiteDetectionsRecent } from "@/hooks/useSiteDetectionsRecent";
import RecentDetectionsTable from "@/components/RecentDetectionsTable";
import {
  RECENT_FILTER_ALL,
  RECENT_FILTER_VESSELS,
  RECENT_FILTER_MAMMALS,
  RECENT_DETECTIONS_LIMIT,
  passesRecentFilter,
} from "@/lib/detections";
import { mergeRecentSeries } from "@/lib/siteDetections";

// ─── Absorbed sub-component ─────────────────────────────────────────────────

const CHIPS = [
  { id: RECENT_FILTER_ALL, label: "All" },
  { id: RECENT_FILTER_VESSELS, label: "Vessels" },
  { id: RECENT_FILTER_MAMMALS, label: "Mammals" },
];

function RecentFilterChips({ value, onChange }) {
  return (
    <div
      className={clsx(
        "inline-flex rounded-[7px] border p-[2px]",
        "border-grey300 bg-grey100",
        "dark:border-grey200",
      )}
    >
      {CHIPS.map((chip) => (
        <button
          key={chip.id}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onChange(chip.id);
          }}
          className={clsx(
            "rounded-[5px] border-none bg-transparent px-12 py-5 font-mono text-[12px] font-medium uppercase tracking-[0.04em] transition-all duration-150",
            value === chip.id
              ? "bg-surface text-textPrimary shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
              : "text-textSecondary hover:text-textPrimary",
          )}
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}

export default function RecentDetectionsCard({
  scoutId,
  authToken,
  onOpenBinInspection,
  // Site (multi-deployment) mode: when provided, the card fetches via the Site
  // bulk endpoint, merges across hydrotwins, and renders an extra htId column.
  siteContext,
}) {
  const isMulti = Boolean(siteContext);
  // For the Scout path, hide the jump button on HT-S devices (no acoustic).
  // For the Site path, leave jump on — individual rows can still be hydrotwin-aware.
  const isHtsDevice = !isMulti && Boolean(scoutId?.toLowerCase().includes('-s-'));
  const [filterId, setFilterId] = useState(RECENT_FILTER_ALL);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 15_000);
    return () => clearInterval(id);
  }, []);

  // Scout data source.
  const scoutQuery = useQuery({
    queryKey: ["recentDetections", scoutId, RECENT_DETECTIONS_LIMIT],
    queryFn: ({ signal }) =>
      fetchRecentDetections(
        scoutId,
        authToken,
        signal,
        RECENT_DETECTIONS_LIMIT,
      ),
    enabled: !isMulti && Boolean(scoutId && authToken),
    refetchInterval: 60_000,
  });

  // Site data source.
  const siteQuery = useSiteDetectionsRecent(
    isMulti ? siteContext.siteId : null,
    isMulti ? siteContext.htIds : [],
    RECENT_DETECTIONS_LIMIT,
  );

  const data = useMemo(() => {
    if (isMulti) {
      return mergeRecentSeries(siteQuery.series, RECENT_DETECTIONS_LIMIT);
    }
    return scoutQuery.data;
  }, [isMulti, siteQuery.series, scoutQuery.data]);

  const isLoading = isMulti ? siteQuery.isLoading : scoutQuery.isLoading;
  const error = isMulti ? siteQuery.error : scoutQuery.error;

  const rows = useMemo(() => {
    const list = data?.detections ?? [];
    return list.filter((d) => passesRecentFilter(filterId, d.category));
  }, [data, filterId]);

  if (!isMulti && !authToken) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="border-b border-grey200 px-20 py-20 font-mono text-[14px] text-textSecondary">
        Loading recent detections…
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-b border-grey200 px-20 py-20 font-mono text-[14px] text-error">
        {error.message || "Could not load recent detections."}
      </div>
    );
  }

  return (
    <div className="border-b border-grey200">
      {/* Header — compact single row with chevron, title, live tag, filter chips */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setIsOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setIsOpen((v) => !v);
          }
        }}
        aria-expanded={isOpen}
        className={clsx(
          "flex cursor-pointer select-none flex-wrap items-center justify-between gap-12 px-20 py-12 transition-colors duration-150 hover:bg-grey100",
          !isOpen && "[&+div]:hidden",
        )}
      >
        <div className="flex items-center gap-10">
          {/* Chevron */}
          <svg
            className={clsx(
              "flex-shrink-0 text-textSecondary transition-transform duration-200",
              !isOpen && "-rotate-90",
            )}
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden
          >
            <path d="M6 9l6 6 6-6" />
          </svg>

          {/* Title + count */}
          <span className="copy-body font-semibold leading-tight text-textPrimary">
            Recent detections
          </span>

          {/* Live tag */}
          <span className="inline-flex items-center gap-5 rounded-[4px] bg-primarySelected px-8 py-3 font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-primary">
            <span
              className="h-[5px] w-[5px] flex-shrink-0 animate-pulse rounded-full bg-primary"
              aria-hidden
            />
            Live · 60s
          </span>
        </div>

        {/* Filter chips */}
        <RecentFilterChips value={filterId} onChange={setFilterId} />
      </div>

      {/* Expanded table */}
      {isOpen && (
        <div className={clsx("border-t border-grey200", !isOpen && "hidden")}>
          <RecentDetectionsTable
            rows={rows}
            nowMs={nowMs}
            onJumpClick={onOpenBinInspection}
            showJump={!isHtsDevice}
            showHydrotwinColumn={isMulti}
            scopedHydrotwins={isMulti ? siteContext.scopedHydrotwins : undefined}
          />
        </div>
      )}

    </div>
  );
}
