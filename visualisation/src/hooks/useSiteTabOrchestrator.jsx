import { useState, useEffect, useMemo } from "react";
import { SITE_TABS, SITE_GRAPHS } from "@/constants/siteChartCards";
import { hydrotwinParticipatesIn } from "@/constants/hydrotwinTypeRegistry";
import { useSiteGraphAvailability } from "@/hooks/useSiteGraphAvailability";
import { useSiteDetectionsOverview } from "@/hooks/useSiteDetectionsOverview";
import { resolveVisibleTabs } from "@/lib/resolveVisibleTabs";
import { detectionsStartIso, detectionsEndIso } from "@/lib/detections";
import { isNumericalVizSite, NUMERICAL_VIZ_TAB } from "@/constants/numericalOverlay";

/**
 * Site tab orchestrator (fleet, multi-deployment).
 *
 * Decides which tabs/graphs render and which tab is selected, from the shared
 * model in resolveVisibleTabs:
 *   visible = structurally applicable (a fleet member's type participates) AND
 *             has data for the range (errors keep a graph visible; empties hide).
 *
 * Availability comes from a cheap limit=1 probe (useSiteGraphAvailability). While
 * probing, `isProbing` is true so the caller can hold a skeleton instead of
 * mounting heavy charts that might immediately be hidden.
 */
export function useSiteTabOrchestrator({ siteId, hydrotwins, startDate, endDate }) {
  const { byMetric, isProbing } = useSiteGraphAvailability({
    siteId,
    hydrotwins,
    startDate,
    endDate,
  });

  // Remembers the user's tab choice; reconciled below when visibility changes.
  const [selectedTab, setSelectedTab] = useState(null);

  // Fleet members that participate in each graph (by hydrotwin type).
  const scopedByGraph = useMemo(() => {
    const map = {};
    for (const g of SITE_GRAPHS) {
      map[g.id] = hydrotwins.filter((h) => hydrotwinParticipatesIn(h.htId, g.id));
    }
    return map;
  }, [hydrotwins]);

  // AI Detections has its own endpoint (not part of the measurement probe), so
  // gauge its range availability here from the same overview the panel renders.
  // The tab shows if ANY scoped twin has ≥1 event in the window; the panel still
  // lets the user pick a subset. Same ISO helpers as SiteDetectionsOverviewSection
  // → identical query key → one shared fetch.
  const detHtIds = useMemo(
    () => (scopedByGraph["aiDetections"] ?? []).map((h) => h.htId),
    [scopedByGraph],
  );
  const detStartIso = useMemo(
    () => (startDate ? detectionsStartIso(startDate) : null),
    [startDate],
  );
  const detEndIso = useMemo(
    () => (endDate ? detectionsEndIso(endDate) : null),
    [endDate],
  );
  const {
    series: detSeries,
    isLoading: detLoading,
    error: detError,
  } = useSiteDetectionsOverview(siteId, detHtIds, detStartIso, detEndIso);
  const detHasData = detSeries.some((s) => Number(s?.data?.totalEvents) > 0);

  const isApplicable = (g) => (scopedByGraph[g.id]?.length ?? 0) > 0;

  const hasData = (g) => {
    const scoped = scopedByGraph[g.id] ?? [];
    if (scoped.length === 0) return false;
    // AI Detections: range-aware — hidden when no scoped twin has events.
    if (g.component === "aiDetections") return detHasData;
    const m = byMetric[g.metric];
    return Boolean(m) && scoped.some((h) => m.htIdsWithData.has(h.htId));
  };

  const hasError = (g) => {
    if (g.component === "aiDetections") return Boolean(detError);
    return Boolean(byMetric[g.metric]?.isError);
  };

  // Keep AI Detections (and thus the Acoustic tab) visible while its overview is
  // still resolving, so it doesn't flash hidden then re-appear.
  const isResolving = (g) =>
    g.component === "aiDetections" ? detLoading : false;

  // Cheap (a handful of graphs) — recompute each render so the closures above
  // always read fresh availability.
  const resolution = resolveVisibleTabs({
    tabs: SITE_TABS,
    graphs: SITE_GRAPHS,
    isApplicable,
    hasData,
    hasError,
    isResolving,
    currentTab: selectedTab,
  });

  // Custom tabs are appended outside the data-availability model — they aren't backed by
  // a measurement probe. The Numerical Visualizer is gated (by build flag in this open
  // build; by site slug in the source app) and always available where enabled. It renders
  // last (highest `order`).
  const customTabs = useMemo(
    () => (isNumericalVizSite(siteId) ? [NUMERICAL_VIZ_TAB] : []),
    [siteId],
  );

  const allTabs = useMemo(
    () => [...resolution.visibleTabs, ...customTabs],
    [resolution.visibleTabs, customTabs],
  );

  // Selected tab honours the user's choice when it's still a valid tab (including a custom
  // one, which `resolution` can't see) and otherwise falls back to the resolver's pick.
  // The custom (Numerical Visualizer) tab must NEVER win the default-tab selection — it is
  // an "extra" that only opens on an explicit click. So the auto-default is ALWAYS a chart
  // tab from the resolver, or null while none have resolved yet; an explicit user choice
  // (including the custom tab) is honoured above it. This kills the race where the custom
  // tab — available before the data probe finishes — would otherwise grab the landing tab
  // and eagerly mount the heavy viewer.
  const selectedTabId =
    selectedTab && allTabs.some((t) => t.id === selectedTab)
      ? selectedTab
      : resolution.selectedTab;

  // Keep the remembered tab aligned with what's actually selectable (first load, or when
  // the chosen tab disappears after a range change). Never clobbers a valid custom choice.
  useEffect(() => {
    if (selectedTabId !== selectedTab) {
      setSelectedTab(selectedTabId);
    }
  }, [selectedTabId, selectedTab]);

  // Group the visible graphs back into per-tab card lists for ChartGrid. Each
  // card's hydrotwin scope is narrowed from "type-participating" to "actually has
  // data for this metric/range" using the availability probe — so the picker (and
  // default selection) only lists units with data. This covers optional sensors
  // (Dissolved Oxygen, Current) and metrics a type nominally supports but lacks
  // (Energy on HT-C). AI Detections has no measurement metric in the probe, so it
  // keeps its full type scope (its own availability is handled separately).
  const cardsByTab = useMemo(() => {
    const out = {};
    for (const g of resolution.visibleGraphs) {
      const scoped = scopedByGraph[g.id] ?? [];
      const avail = byMetric[g.metric]?.htIdsWithData;
      const dataScoped =
        avail && avail.size > 0 ? scoped.filter((h) => avail.has(h.htId)) : scoped;
      (out[g.tabId] ??= []).push({
        card: g,
        scopedHydrotwins: dataScoped,
      });
    }
    return out;
  }, [resolution.visibleGraphs, scopedByGraph, byMetric]);

  return {
    tabs: allTabs,
    cardsByTab,
    selectedTab: selectedTabId,
    setSelectedTab,
    isProbing,
    // A site with no chart data still has content if a custom tab is present.
    hasNoData: resolution.hasNoData && customTabs.length === 0,
  };
}
