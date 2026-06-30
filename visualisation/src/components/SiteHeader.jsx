import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { PrimaryButton } from "@/components/Buttons";
import { RefreshIcon } from "@/components/Icons";
import { useWindowSize } from "@/hooks/useWindowSize";

/**
 * Top chrome for the single-site view.
 *
 * Layout:
 *   Left   — configurable page title, with the connected status pill bar inline
 *            to the right of the heading
 *   Right  — Refresh CTA (invalidates the site-scoped queries)
 *
 * Branding (project/site name, alerts bell, back button) was removed for the
 * open build; the title is supplied via config (VITE_PAGE_TITLE).
 */

const STATUS_BAR_ITEMS = [
  { key: "active",          label: "Active",          dotColor: "#38bc72", dotGlow: "0 0 0 3px rgba(29,158,117,0.15)" },
  { key: "charging",        label: "Charging",        dotColor: "#3a7bd5", dotGlow: "0 0 0 3px rgba(55,138,221,0.15)" },
  { key: "low_battery",     label: "Low Battery",     dotColor: "#fc8923", dotGlow: "0 0 0 3px rgba(239,159,39,0.15)" },
  { key: "unresponsive",    label: "Unresponsive",    dotColor: "#777979", dotGlow: "0 0 0 3px rgba(180,178,169,0.15)" },
  { key: "maintenance",     label: "Maintenance",     dotColor: "#b5b8b8", dotGlow: "0 0 0 3px rgba(181,184,184,0.15)" },
  { key: "decommissioned",  label: "Decommissioned",  dotColor: "#555858", dotGlow: "0 0 0 3px rgba(85,88,88,0.15)" },
];

export default function SiteHeader({ title, statusCounts }) {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const windowSize = useWindowSize();
  const isSmallScreen = windowSize != null && windowSize < 768;

  const visibleItems = STATUS_BAR_ITEMS.filter(
    ({ key }) => (statusCounts?.[key] ?? 0) > 0,
  );

  // Refresh — invalidates every site-scoped query so the rail and chart grid refetch.
  const handleRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      await queryClient.invalidateQueries({
        predicate: (q) => {
          const key = q.queryKey?.[0];
          return typeof key === "string" && (key === "site" || key.startsWith("site-"));
        },
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 24,
        padding: isSmallScreen ? "10px 0 16px" : "24px 0 22px",
        flexWrap: "wrap",
      }}
    >
      {/* Title block — heading with the status pill bar inline to its right */}
      <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap", minWidth: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <h1
            style={{
              fontSize: isSmallScreen ? 23 : 32,
              fontWeight: 600,
              margin: 0,
              letterSpacing: "-0.02em",
              color: "var(--text-primary)",
              lineHeight: 1.1,
            }}
          >
            {title}
          </h1>
        </div>

        {/* Connected pill bar — inline, to the right of the heading */}
        {visibleItems.length > 0 && (
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            flexWrap: "wrap",
            rowGap: isSmallScreen ? 4 : 0,
            fontSize: 12.5,
            color: "var(--text-secondary)",
            background: "var(--surface)",
            border: "0.5px solid var(--grey-300)",
            borderRadius: 8,
            padding: "6px 4px",
          }}>
            {visibleItems.map(({ key, label, dotColor, dotGlow }, idx) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: isSmallScreen ? "0 10px" : "0 12px",
                  borderRight:
                    !isSmallScreen && idx < visibleItems.length - 1
                      ? "0.5px solid var(--grey-300)"
                      : "none",
                }}
              >
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: dotColor,
                  boxShadow: dotGlow,
                  flexShrink: 0,
                  display: "inline-block",
                }} />
                <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                  {statusCounts[key]}
                </span>
                &nbsp;{label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right-side actions — Refresh only. */}
      <div className="flex w-full flex-nowrap items-center justify-end gap-8 768:w-auto 768:ml-auto">
        <PrimaryButton
          size="medium"
          onClick={handleRefresh}
          disabled={isRefreshing}
          extraClass="flex items-center justify-center gap-x-6 whitespace-nowrap"
        >
          <RefreshIcon className={isRefreshing ? "animate-spin" : ""} />
          {isRefreshing ? "Refreshing..." : "Refresh Data"}
        </PrimaryButton>
      </div>
    </div>
  );
}
