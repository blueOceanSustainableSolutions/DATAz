import clsx from "clsx";
import { getCategoryColor, getCategoryLabel } from "@/lib/detections";

// Categories Shown In Overview Stats for AI Detections
const OVERVIEW_DISPLAY_CATEGORIES = new Set([
  "vessel", "vessels", "dolphin", "dolphins",
]);

function pad2(n) {
  return String(n).padStart(2, "0");
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatPeakTimestamp(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${MONTHS[d.getUTCMonth()]} ${pad2(d.getUTCDate())} · ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
}

/**
 * Returns a human-friendly duration string for the overview window.
 *   < 24 h  → "Xh"
 *   ≥ 24 h  → "Xd"  (rounded to nearest day)
 */
function formatWindowDuration(overview) {
  const start = overview?.window?.startDate;
  const end   = overview?.window?.endDate;
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms <= 0) return "—";
  const hours = ms / 3_600_000;
  if (hours < 24) return `${Math.max(1, Math.round(hours))}h`;
  return `${Math.round(hours / 24)}d`;
}

function MetaDivider() {
  return <div className="hidden h-[22px] w-px flex-shrink-0 bg-grey300 768:block" aria-hidden />;
}

function MetaRow({ label, children, valueClassName }) {
  return (
    <div className="flex flex-col gap-3">
      <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-textSecondary">
        {label}
      </span>
      <div
        className={clsx(
          "inline-flex items-baseline gap-6 font-mono text-[14px] font-medium tabular-nums text-textPrimary",
          valueClassName,
        )}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * Stats card — design reference: .stats-bar, .stats-meta-strip, .stats-distribution,
 * .stacked-bar, .distribution-legend.
 */
export default function OverviewStatsCard({ overview, isLoading, error }) {
  if (isLoading) {
    return (
      <div className="border-b border-grey200 px-20 py-20 font-mono text-[14px] text-textSecondary">
        Loading overview…
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-b border-grey200 px-20 py-20 font-mono text-[14px] text-error">
        {error.message || "Could not load overview."}
      </div>
    );
  }

  if (!overview) {
    return null;
  }

  const uniqueClasses = overview.uniqueClasses ?? 0;
  const devActive = overview.devices?.active ?? 0;
  const devTotal = overview.devices?.total ?? 0;
  const intervalMin = overview.intervalMinutes ?? "—";
  const windowLabel = formatWindowDuration(overview);
  const peak = overview.leadingCategoryPeak;
  const peakPct =
    peak?.intensityPercentage != null
      ? Math.round(Number(peak.intensityPercentage))
      : null;


  // Filter Categories To Only Show The Display Categories
  const categories = [...(overview.byCategory || [])]
    .filter((row) =>
      OVERVIEW_DISPLAY_CATEGORIES.has(String(row.category || "").toLowerCase()),
    )
    .sort((a, b) => (b.events || 0) - (a.events || 0));
    
  const total = categories.reduce((sum, row) => sum + (Number(row.events) || 0), 0);
  const leadingCat = categories.length > 0 ? categories[0].category : null;
  const peakColor = getCategoryColor(leadingCat);

  return (
    <div className="border-b border-grey200">
      {/* Meta strip — bg-grey100 matches design .stats-meta-strip */}
      <div className="flex flex-col gap-12 border-b border-grey200 bg-grey100 px-20 py-14 768:flex-row 768:items-center 768:justify-between 768:gap-20">
        <div className="flex min-w-0 flex-wrap items-center gap-20">
          <MetaRow label="Classes">{uniqueClasses}</MetaRow>
          <MetaDivider />
          <MetaRow label="Devices">
            {devActive} / {devTotal}
          </MetaRow>
          <MetaDivider />
          <MetaRow label="Window">
            {windowLabel}
          </MetaRow>
          <MetaDivider />
          <MetaRow label="Interval">
            {typeof intervalMin === "number" ? `${intervalMin} min` : intervalMin}
          </MetaRow>
          <MetaDivider />
          <MetaRow label="Total">{total.toLocaleString()}</MetaRow>
          {peakPct != null && peak?.ingestedAt && (
            <>
              <MetaDivider />
              <MetaRow label="Peak">
                <span className="inline-flex items-baseline gap-6 font-mono text-[14px] font-medium text-textPrimary">
                  <span
                    className="relative top-[-1px] h-6 w-6 flex-shrink-0 rounded-full"
                    style={{ background: peakColor }}
                    aria-hidden
                  />
                  {peakPct}% @ {formatPeakTimestamp(peak.ingestedAt)}
                  {peak.htId && (
                    <span className="ml-4 text-textSecondary">· {peak.htId}</span>
                  )}
                </span>
              </MetaRow>
            </>
          )}
        </div>

        {total > 0 && leadingCat && (
          <div className="inline-flex self-start rounded-[7px] border border-grey300 bg-surface p-[2px] 768:self-auto dark:border-grey200">
            <span className="inline-flex items-center gap-6 whitespace-nowrap rounded-[5px] bg-primarySelected px-12 py-5 font-mono text-[12px] font-medium text-primary">
              <span
                className="h-[7px] w-[7px] flex-shrink-0 rounded-full"
                style={{ background: getCategoryColor(leadingCat) }}
                aria-hidden
              />
              {getCategoryLabel(leadingCat)} leading
            </span>
          </div>
        )}
      </div>

      {/* Distribution */}
      <div className="px-20 py-16">
        <div className="flex min-w-0 flex-col gap-12">
          {/* Stacked bar */}
          <div className="flex h-16 w-full overflow-hidden rounded-[4px] bg-grey200 shadow-[inset_0_0_0_1px] shadow-grey300">
            {categories
              .map((row) => ({
                row,
                pct: total > 0 ? ((Number(row.events) || 0) / total) * 100 : 0,
              }))
              .filter(({ pct }) => pct > 0)
              .map(({ row, pct }, idx) => {
                const cat = String(row.category || "").toLowerCase();
                const bg = getCategoryColor(cat);
                return (
                  <div
                    key={cat}
                    title={`${getCategoryLabel(cat)}: ${row.events} (${pct.toFixed(1)}%)`}
                    className="h-full transition-[width] duration-300 ease-out hover:brightness-110"
                    style={{
                      width: `${pct}%`,
                      background: bg,
                      borderLeft:
                        idx > 0 ? "1px solid rgba(255,255,255,0.6)" : undefined,
                    }}
                  />
                );
              })}
          </div>

          {/* Legend grid — 2 columns per design .distribution-legend */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-y-12 gap-x-20">
            {categories.map((row) => {
              const cat = String(row.category || "").toLowerCase();
              const pct =
                total > 0
                  ? ((Number(row.events) || 0) / total) * 100
                  : Number(row.percentageOfTotal) || 0;
              return (
                <div key={cat} className="flex min-w-0 flex-col gap-3">
                  <div className="flex min-w-0 items-center gap-6 font-mono text-[12px] tracking-[0.02em] text-textSecondary">
                    <span
                      className="h-8 w-8 flex-shrink-0 rounded-full"
                      style={{ background: getCategoryColor(cat) }}
                      aria-hidden
                    />
                    <span className="truncate">{getCategoryLabel(cat)}</span>
                  </div>
                  <div className="flex items-baseline gap-6 font-mono text-[14px] font-medium text-textPrimary">
                    <span>{Number(row.events) || 0}</span>
                    <span className="text-[12px] font-normal text-textSecondary">
                      {pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {categories.length === 0 && (
            <p className="text-[13px] text-textSecondary">
              No category breakdown for this range.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
