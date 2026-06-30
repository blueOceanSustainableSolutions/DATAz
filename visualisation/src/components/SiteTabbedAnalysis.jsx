import { lazy, Suspense, useMemo } from "react";
import SiteTabBar from "@/components/SiteTabBar";
import CustomDatepickerScoutPage from "@/components/CustomDatepickerScoutPage";
import Spinner from "@/components/Spinner";
import { ResetIcon } from "@/components/Icons";
import { NUMERICAL_VIZ_TAB } from "@/constants/numericalOverlay";

// Lazy + code-split: the Numerical Visualizer pulls in the MapLibre overlay player, so
// its chunk loads only when its (gated) tab is first selected — keeping it off the
// critical path for every other render.
const NumericalOverlayViewer = lazy(
  () => import("@/components/NumericalOverlayViewer"),
);

function NumericalOverlayPanel() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[320px] items-center justify-center">
          <Spinner isLoading size={32} />
        </div>
      }
    >
      <NumericalOverlayViewer />
    </Suspense>
  );
}

/**
 * Hero organism for the site view. Runs the tab orchestrator (which probes
 * per-graph data availability) and renders only the tabs/graphs that have data
 * for the selected range, with the shared date-range picker in the tab bar's
 * right slot. While probing — or when the fleet/range has nothing to show — it
 * falls back to a state row that keeps the picker available so the user can
 * widen the range.
 *
 * A "Reset to Today" shortcut sits beside the picker — matching the
 * single-deployment page's "Reset to Today" button.
 */

/** Start of today (UTC) → now. Matches pages/site/[id].js defaultDateRange(). */
function getTodayRange() {
  const now = new Date();
  const startOfToday = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      0,
      0,
      0,
      0,
    ),
  );
  return { startOfToday, endNow: now };
}

/** State row used while probing / when there is nothing to show. Keeps the date
 *  picker visible so the user can change the range. */
function AnalysisStateRow({ datePicker, children }) {
  return (
    <div>
      <div className="p-8 768:p-24 flex justify-end">{datePicker}</div>
      <div className="flex min-h-[240px] items-center justify-center px-16 pb-24 text-center">
        {children}
      </div>
    </div>
  );
}

export default function SiteTabbedAnalysis({
  orchestrator,
  siteId,
  hydrotwins,
  isLoading,
  startDate,
  endDate,
  handleDatesApply,
}) {
  const { tabs, cardsByTab, selectedTab, setSelectedTab, isProbing } = orchestrator;

  // Custom (non-ChartGrid) tab panels, keyed by tab id. Only built when the orchestrator
  // actually exposed the tab (it's gated), so other builds never reference the viewer.
  const customPanels = useMemo(() => {
    const panels = {};
    if (tabs.some((t) => t.id === NUMERICAL_VIZ_TAB.id)) {
      panels[NUMERICAL_VIZ_TAB.id] = <NumericalOverlayPanel />;
    }
    return panels;
  }, [tabs]);

  // Reset is offered only when the active range differs from the default
  // "today" window (start ≠ today 00:00 UTC, or end is not today).
  const canReset = (() => {
    const { startOfToday } = getTodayRange();
    const startMs =
      startDate instanceof Date
        ? startDate.getTime()
        : new Date(startDate).getTime();
    if (Number.isNaN(startMs) || startMs !== startOfToday.getTime()) return true;

    const end = endDate instanceof Date ? endDate : new Date(endDate);
    const now = new Date();
    const endIsToday =
      end.getUTCFullYear() === now.getUTCFullYear() &&
      end.getUTCMonth() === now.getUTCMonth() &&
      end.getUTCDate() === now.getUTCDate();
    return !endIsToday;
  })();

  const handleResetToToday = () => {
    const { startOfToday, endNow } = getTodayRange();
    handleDatesApply(startOfToday, endNow);
  };

  const datePicker = (
    <div className="flex w-full items-center gap-8 1024:w-fit">
      {canReset && (
        <button
          type="button"
          onClick={handleResetToToday}
          title="Reset the date range to today"
          className="shrink-0 flex items-center gap-6 whitespace-nowrap rounded-8 border border-grey300 bg-surface px-12 py-13 copy-body text-textPrimary media-hover:hover:bg-grey100 transition"
        >
          <ResetIcon />
          Reset to Today
        </button>
      )}
      <div className="min-w-0 flex-1 1024:flex-none">
        <CustomDatepickerScoutPage
          key={siteId}
          defaultDateStart={startDate}
          defaultDateEnd={endDate}
          handleDatesApply={handleDatesApply}
        />
      </div>
    </div>
  );

  // Still loading the site, or probing availability — hold a skeleton rather
  // than mount heavy charts that might be hidden a moment later.
  if (isLoading || isProbing) {
    return (
      <AnalysisStateRow datePicker={datePicker}>
        <Spinner isLoading size={32} />
      </AnalysisStateRow>
    );
  }

  // When the orchestrator surfaced at least one tab — chart tabs with data, or a gated
  // custom tab (Numerical Visualizer) that doesn't depend on the measurement probe —
  // render the tab bar. Otherwise show an explanatory state that keeps the picker handy.
  if (tabs.length === 0) {
    return (
      <AnalysisStateRow datePicker={datePicker}>
        <p className="copy-body text-textSecondary">
          {!hydrotwins || hydrotwins.length === 0
            ? "No deployments at this site yet."
            : "No data available for the selected range. Try a different date range."}
        </p>
      </AnalysisStateRow>
    );
  }

  return (
    <SiteTabBar
      tabs={tabs}
      cardsByTab={cardsByTab}
      selectedTab={selectedTab}
      setSelectedTab={setSelectedTab}
      siteId={siteId}
      startDate={startDate}
      endDate={endDate}
      rightSlot={datePicker}
      customPanels={customPanels}
    />
  );
}
