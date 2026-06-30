"use client";

import { useMemo } from "react";
import clsx from "clsx";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";

/**
 * Interactive deployment legend rendered under BinInspectionBeeswarmChart.
 *
 * One chip per deployment present in the bin's events. Each chip shows a
 * colour swatch (matching the beeswarm dot's colour and shape — solid for
 * HT-C, hollow with dashed stroke for HT-S), the htId, and the per-bin
 * event count. Click a chip to toggle isolation:
 *   - click an inactive chip while no filter is set → isolate that htId
 *   - click the active chip → clear the filter (show all)
 * An "All" chip is rendered first; click it to clear the filter at any time.
 *
 * The selected `depFilter` is owned by the parent so isolation survives
 * bin prev/next navigation.
 */
export default function BinInspectionDeploymentLegend({
  events,
  scopedHydrotwins,
  depFilter,
  onDepFilterChange,
}) {
  // Group events by htId; counts drive the chip label.
  const groups = useMemo(() => {
    const map = new Map();
    for (const ev of events ?? []) {
      const htId = ev.htId ?? null;
      if (!htId) continue;
      map.set(htId, (map.get(htId) || 0) + 1);
    }
    // Stable sort by htId for deterministic chip order.
    return [...map.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([htId, count]) => ({ htId, count }));
  }, [events]);

  if (groups.length === 0) return null;

  const handleToggle = (htId) => {
    if (!onDepFilterChange) return;
    onDepFilterChange(depFilter === htId ? null : htId);
  };

  return (
    <div className="flex flex-wrap items-center gap-8 border-t border-grey200 bg-grey100 px-20 py-10 dark:border-grey300">
      <button
        type="button"
        onClick={() => onDepFilterChange?.(null)}
        className={clsx(
          "inline-flex items-center gap-6 rounded-[6px] border px-10 py-4 font-mono text-[11px] font-medium tracking-[0.04em] transition-colors duration-150",
          depFilter == null
            ? "border-primary bg-primarySelected text-primary"
            : "border-grey300 bg-surface text-textSecondary hover:text-textPrimary dark:border-grey200",
        )}
        aria-pressed={depFilter == null}
      >
        All
        <span className="font-normal opacity-70">·</span>
        <span className="tabular-nums">{events?.length ?? 0}</span>
      </button>

      {groups.map(({ htId, count }) => {
        const color = scopedHydrotwins
          ? getOverlayColor({ htId, scopedHydrotwins })
          : "#888888";
        const isActive = depFilter === htId;

        return (
          <button
            key={htId}
            type="button"
            onClick={() => handleToggle(htId)}
            className={clsx(
              "inline-flex items-center gap-6 rounded-[6px] border px-10 py-4 font-mono text-[11px] font-medium tracking-[0.04em] transition-colors duration-150",
              isActive
                ? "border-primary bg-primarySelected text-primary"
                : "border-grey300 bg-surface text-textPrimary hover:bg-grey200 dark:border-grey200",
            )}
            aria-pressed={isActive}
            title={isActive ? "Click to clear isolation" : `Isolate ${htId}`}
          >
            {/* Swatch matches the dot visual — solid filled circle for every htId. */}
            <span
              className="h-[10px] w-[10px] flex-shrink-0 rounded-full"
              style={{ background: color }}
              aria-hidden
            />
            <span>{htId}</span>
            <span className="font-normal opacity-70">·</span>
            <span className="tabular-nums">{count}</span>
          </button>
        );
      })}
    </div>
  );
}
