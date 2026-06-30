import { cn } from "@/lib/classnames";

/**
 * SegmentedToggle — smooth pill segmented control.
 *
 * Matches the design's .hts-series-toggle: a subtle bordered container with
 * the active option raised on a white surface + soft shadow. Used in chart
 * card headers to switch series/views (e.g. Wave Period Peak/Mean, Dissolved
 * Oxygen Concentration/Quality Factor). Theme-aware via design tokens.
 *
 * Props:
 *   options   {{ key: string, label: string }[]}
 *   value     string — the active option key
 *   onChange  (key) => void
 */
export default function SegmentedToggle({ options = [], value, onChange, ariaLabel }) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-0 rounded-[6px] border border-grey300 bg-grey100 p-2"
    >
      {options.map((opt) => {
        const active = opt.key === value;
        return (
          <button
            key={opt.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange?.(opt.key)}
            className={cn(
              "whitespace-nowrap select-none rounded-4 px-10 py-5 copy-small font-medium transition",
              active
                ? "bg-surface text-textPrimary shadow-sm"
                : "text-textSecondary media-hover:hover:text-textPrimary",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
