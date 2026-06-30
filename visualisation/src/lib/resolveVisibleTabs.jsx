// Pure, page-agnostic tab/graph visibility resolver shared by the Scout
// (single-deployment) and Site (fleet) tab orchestrators. It is the single
// decision point for "which graphs and tabs are visible, and which tab is
// selected" given structural applicability + per-graph data availability.
//
// Authored as .mjs so it runs directly under `node --test` for self-driven
// verification — the webapp's `.js` sources are ESM transpiled by Next and
// can't be executed by bare Node. Next resolves the `.mjs` extension, so app
// imports (`@/utils/resolveVisibleTabs`) are unaffected.

/**
 * @typedef {Object} TabDef
 * @property {string} id
 * @property {string} [label]
 * @property {number} [order]
 */

/**
 * @typedef {Object} GraphDef
 * @property {string} id
 * @property {string} tabId  Which tab this graph belongs to (must match a TabDef.id).
 */

/**
 * Decide which graphs/tabs render and which tab is selected.
 *
 * Rules:
 *  - A graph is visible when it is structurally applicable AND it is either
 *    still resolving, has data, or has errored.
 *  - An applicable graph that has resolved with no data and no error is HIDDEN.
 *  - A tab is visible when at least one of its graphs is visible.
 *  - Errors are never hidden — a failed/down feed surfaces as an error state
 *    rather than silently disappearing (the safeguard for the hide-empty policy).
 *  - Graph order is preserved from the input array (array order == render order).
 *  - Tabs are ordered by `order`. The selected tab is the current one if it is
 *    still visible, otherwise the first visible tab.
 *
 * @param {Object} params
 * @param {TabDef[]} params.tabs
 * @param {GraphDef[]} params.graphs
 * @param {(g: GraphDef) => boolean} [params.isApplicable]  Device-type capability gate.
 * @param {(g: GraphDef) => boolean} [params.hasData]       Confirmed data for the range.
 * @param {(g: GraphDef) => boolean} [params.isResolving]   Still loading/probing.
 * @param {(g: GraphDef) => boolean} [params.hasError]      Fetch/probe errored.
 * @param {string|null} [params.currentTab]                 Currently selected tab id.
 * @returns {{ visibleGraphs: GraphDef[], visibleTabs: TabDef[], selectedTab: string|null, hasNoData: boolean }}
 */
export function resolveVisibleTabs({
  tabs = [],
  graphs = [],
  isApplicable = () => true,
  hasData = () => false,
  isResolving = () => false,
  hasError = () => false,
  currentTab = null,
}) {
  const isGraphVisible = (g) =>
    isApplicable(g) && (isResolving(g) || hasData(g) || hasError(g));

  // Preserve config order — the input array order is the on-screen render order.
  const visibleGraphs = graphs.filter(isGraphVisible);

  const tabsWithVisibleGraph = new Set(visibleGraphs.map((g) => g.tabId));

  const visibleTabs = tabs
    .filter((t) => tabsWithVisibleGraph.has(t.id))
    .slice()
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  const currentStillVisible =
    currentTab != null && visibleTabs.some((t) => t.id === currentTab);

  const selectedTab = currentStillVisible
    ? currentTab
    : visibleTabs[0]?.id ?? null;

  return {
    visibleGraphs,
    visibleTabs,
    selectedTab,
    hasNoData: visibleTabs.length === 0,
  };
}
