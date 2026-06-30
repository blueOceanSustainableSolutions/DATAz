import { TabRenderer } from "@/components/TabRenderer";
import ChartGrid from "@/components/ChartGrid";

/**
 * Renders the site-page tabs and their chart grids. Only the tabs the
 * orchestrator (useSiteTabOrchestrator) marked visible are passed in, and tab
 * selection is controlled by the orchestrator so the choice survives date-range
 * changes and a hidden tab can never be selected.
 *
 * The `rightSlot` prop (date picker) is forwarded into TabRenderer so it sits
 * flush-right in the tab bar row.
 *
 * `customPanels` lets a tab opt out of the ChartGrid and render its own panel
 * (keyed by tab id) — used for the gated Numerical Visualizer tab, whose content is
 * a map, not charts. Custom panels still unmount when their tab is inactive, so heavy
 * content (e.g. MapLibre) only mounts on selection.
 */
export default function SiteTabBar({
  tabs,
  cardsByTab,
  selectedTab,
  setSelectedTab,
  siteId,
  startDate,
  endDate,
  rightSlot,
  customPanels = {},
}) {
  const rendererTabs = tabs.map((t) => ({
    key: t.id,
    name: t.label,
    panel: customPanels[t.id] ?? (
      <ChartGrid
        cards={cardsByTab[t.id] ?? []}
        siteId={siteId}
        startDate={startDate}
        endDate={endDate}
      />
    ),
  }));

  const selectedIndex = Math.max(
    0,
    tabs.findIndex((t) => t.id === selectedTab),
  );

  return (
    <TabRenderer
      tabs={rendererTabs}
      rightSlot={rightSlot}
      selectedIndex={selectedIndex}
      onChange={(idx) => setSelectedTab(tabs[idx]?.id ?? null)}
      flushHeader
    />
  );
}
