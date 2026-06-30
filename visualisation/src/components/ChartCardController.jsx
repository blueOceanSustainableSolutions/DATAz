import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import ChartCard from "@/components/charts/ChartCard";
import HydrotwinPicker from "@/components/HydrotwinPicker";
import { OutlineButton } from "@/components/Buttons";
import { Alert, AlertDescription, AlertTitle } from "@/components/Alert";
import { useSiteHistoricalSeries } from "@/hooks/useSiteHistoricalSeries";
import { getHydrotwinTypeKey } from "@/constants/hydrotwinTypeRegistry";

import BroadbandSPLChart from "@/components/charts/BroadbandSPLChart";
import OctaveBandsChart from "@/components/charts/OctaveBandsChart";
import SpectrogramChart from "@/components/charts/SpectrogramChart";
import WaveHeightChart from "@/components/charts/WaveHeightChart";
import WavePeriodChart from "@/components/charts/WavePeriodChart";
import WaveDirectionChart from "@/components/charts/WaveDirectionChart";
import WindChart from "@/components/charts/WindChart";
import BarometerChart from "@/components/charts/BarometerChart";
import DissolvedOxygenChart from "@/components/charts/DissolvedOxygenChart";
import CurrentChart from "@/components/charts/CurrentChart";
import TempHumidityChart from "@/components/charts/TempHumidityChart";
import EnergyChart from "@/components/charts/EnergyChart";
import AnomalyChart from "@/components/charts/AnomalyChart";
import SiteDetectionsOverviewSection from "@/components/SiteDetectionsOverviewSection";

const CHART_COMPONENTS = {
  broadbandSPL: BroadbandSPLChart,
  octaveBands: OctaveBandsChart,
  spectrogram: SpectrogramChart,
  anomaly: AnomalyChart,
  waveHeight: WaveHeightChart,
  wavePeriod: WavePeriodChart,
  waveDirection: WaveDirectionChart,
  wind: WindChart,
  barometric: BarometerChart,
  dissolvedOxygen: DissolvedOxygenChart,
  current: CurrentChart,
  tempHumidity: TempHumidityChart,
  energy: EnergyChart,
};

export default function ChartCardController({
  card,
  siteId,
  scopedHydrotwins,
  startDate,
  endDate,
}) {
  const { id, title, subtitle, icon, mode, component, metric } = card;

  const isRibbonSlot = component === "ribbon";
  const isAiDetectionsSlot = component === "aiDetections";
  // AI Detections has its own internal data hooks (overview/bins/recent/bin_inspection),
  // so it doesn't use the generic /measurements/:metric fan-out below.
  const skipFetch = isRibbonSlot || isAiDetectionsSlot;

  // Start empty — populated by the effect below once scopedHydrotwins arrives.
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const initializedRef = useRef(false);

  // scopedHydrotwins is [] on first render while the site data is still loading.
  // Always seed with all HTs so the initial query covers everyone — for single-select
  // this acts as a discovery pass; the effect below narrows to one after data arrives.
  useEffect(() => {
    if (initializedRef.current || scopedHydrotwins.length === 0) return;
    initializedRef.current = true;
    setSelectedIds(new Set(scopedHydrotwins.map((h) => h.htId)));
  }, [scopedHydrotwins]);

  // Extra controls injected by individual chart components (e.g. band picker, period toggle).
  const [extraControls, setExtraControls] = useState(null);

  // Unique hydrotwin types present in this card's scope.
  const htTypes = useMemo(
    () =>
      [...new Set(scopedHydrotwins.map((h) => getHydrotwinTypeKey(h.htId)).filter(Boolean))].sort(),
    [scopedHydrotwins],
  );

  const activeHtIds = useMemo(() => [...selectedIds], [selectedIds]);

  const { series, isLoading, isTooManyRows, error } = useSiteHistoricalSeries(
    siteId,
    skipFetch ? null : metric,
    activeHtIds,
    startDate,
    endDate,
  );

  // Show spinner only while the site is still loading (scopedHydrotwins not yet arrived).
  // If scopedHydrotwins are loaded but the user deselected everything, show an empty
  // state message instead — do NOT spin forever.
  const effectiveLoading =
    isLoading || (activeHtIds.length === 0 && scopedHydrotwins.length === 0 && !skipFetch);

  // For single-select cards: run a one-time discovery pass across all HTs to learn
  // which actually have data, then freeze the picker from that result and narrow
  // selection to the first HT with data.
  const [knownDataIds, setKnownDataIds] = useState(null);
  const discoveryDoneRef = useRef(false);

  // Reset discovery when the site or metric changes so the picker doesn't stay
  // frozen on stale results after navigation.
  useEffect(() => {
    discoveryDoneRef.current = false;
    setKnownDataIds(null);
  }, [siteId, metric]);

  useEffect(() => {
    if (discoveryDoneRef.current || isLoading || mode !== "single" || series.length === 0) return;
    const withData = series.filter((s) => s.readings?.length > 0).map((s) => s.htId);
    discoveryDoneRef.current = true;
    // Freeze picker to HTs with data; fall back to all if none returned data.
    setKnownDataIds(new Set(withData.length > 0 ? withData : scopedHydrotwins.map((h) => h.htId)));
    // Narrow selection to a single HT (the first with data).
    const first = withData[0] ?? scopedHydrotwins[0]?.htId;
    if (first) setSelectedIds(new Set([first]));
  }, [series, isLoading, mode, scopedHydrotwins]);

  // pickerHydrotwins:
  //   single-select — use the frozen discovery result so the picker stays stable
  //                   even after selection narrows to one HT.
  //   multi-select  — always show the full scope list. Filtering by query results
  //                   would remove deselected HTs from the picker, making them
  //                   impossible to re-select.
  const pickerHydrotwins = useMemo(() => {
    if (mode === "single" && knownDataIds !== null) {
      const filtered = scopedHydrotwins.filter((h) => knownDataIds.has(h.htId));
      return filtered.length > 0 ? filtered : scopedHydrotwins;
    }
    return scopedHydrotwins;
  }, [scopedHydrotwins, mode, knownDataIds]);

  const ChartComponent = CHART_COMPONENTS[id] ?? null;

  // SPL cards keep their controls stacked below the header on mobile — their
  // band/percentile pickers are too wide to share the header row. Every other
  // card shows controls inline on the right at all breakpoints (like web).
  const stackControlsOnMobile = id === "broadbandSPL" || id === "octaveBands";

  const noneSelected = !skipFetch && scopedHydrotwins.length > 0 && activeHtIds.length === 0;
  const chartEmptyMessage = noneSelected
    ? "Select at least one hydrotwin to show data."
    : "No data in the selected range.";

  // AI Detections fetches via its own hooks (skipFetch) but still scopes by
  // hydrotwin selection, so it shows the picker/quick-filters like every other
  // multi card. Only the "coming soon" ribbon slot has no controls.
  const showPicker = !isRibbonSlot && pickerHydrotwins.length > 0;
  // Quick-filters mirror the design's bulk shortcuts: shown for every
  // multi-select graph that has at least two deployments in scope. Per-type
  // buttons ("All HT-S"…) only when more than one type is in scope; the plain
  // "All" otherwise. Scope is participation-derived in ChartGrid, so this
  // tracks the deployments a given graph actually shows.
  const showBulk = mode === "multi" && !isRibbonSlot && scopedHydrotwins.length >= 2;
  const showTypeButtons = showBulk && htTypes.length > 1;

  const isTypeActive = useCallback((type) => {
    const typeIds = scopedHydrotwins
      .filter((h) => getHydrotwinTypeKey(h.htId) === type)
      .map((h) => h.htId);
    if (typeIds.length !== selectedIds.size) return false;
    return typeIds.every((id) => selectedIds.has(id));
  }, [scopedHydrotwins, selectedIds]);
  const isAllActive = selectedIds.size === scopedHydrotwins.length;

  const hasControls = showBulk || extraControls || showPicker;

  // Suppress the entire card once we know this metric has no data at all.
  // Guards: must have finished loading, must have actually queried something,
  // and the API must have responded with entries (all empty).
  // NOTE: this must come after all hooks above.
  const allSeriesEmpty =
    !effectiveLoading &&
    !isTooManyRows &&
    !skipFetch &&
    activeHtIds.length > 0 &&
    series.length > 0 &&
    series.every((s) => (s.readings?.length ?? 0) === 0);

  if (allSeriesEmpty) {
    return (
      <ChartCard icon={icon} title={title} subtitle={subtitle} stackControlsOnMobile={stackControlsOnMobile}>
        <div className="flex min-h-160 items-center justify-center">
          <p className="copy-small text-textSecondary">No data available for the selected range.</p>
        </div>
      </ChartCard>
    );
  }

  return (
    <ChartCard
      icon={icon}
      title={title}
      subtitle={subtitle}
      stackControlsOnMobile={stackControlsOnMobile}
      controls={
        hasControls ? (
          <div className="flex flex-wrap items-center gap-6">
            {showBulk && (
              <>
                {showTypeButtons &&
                  htTypes.map((type) => (
                    <OutlineButton
                      key={type}
                      size="small"
                      onClick={() =>
                        setSelectedIds(
                          new Set(
                            scopedHydrotwins
                              .filter((h) => getHydrotwinTypeKey(h.htId) === type)
                              .map((h) => h.htId),
                          ),
                        )
                      }
                      extraClass={isTypeActive(type) ? "!bg-primarySelected !text-primary !border-primary" : ""}
                    >
                      All {type}
                    </OutlineButton>
                  ))}
                <OutlineButton
                  size="small"
                  onClick={() => setSelectedIds(new Set(scopedHydrotwins.map((h) => h.htId)))}
                  extraClass={isAllActive ? "!bg-primarySelected !text-primary !border-primary" : ""}
                >
                  All
                </OutlineButton>
              </>
            )}
            {extraControls}
            {showPicker && (
              <HydrotwinPicker
                hydrotwins={pickerHydrotwins}
                selectedIds={selectedIds}
                onChange={setSelectedIds}
                mode={mode}
              />
            )}
          </div>
        ) : null
      }
    >
      {isTooManyRows && (
        <div className="flex items-center justify-center py-24 text-center">
          <p className="copy-small text-textSecondary" style={{ maxWidth: 280 }}>
            Too many data points. Narrow the date range or reduce the hydrotwin
            selection.
          </p>
        </div>
      )}

      {/* A fetch failure is kept distinct from an empty range: an error is shown
          (never hidden) so a down feed surfaces instead of looking like "no data". */}
      {error && !isTooManyRows && !skipFetch && (
        <div className="flex items-center justify-center py-24">
          <Alert variant="error" className="!w-fit max-w-md">
            <AlertTitle className="copy-body">Couldn&apos;t load this chart</AlertTitle>
            <AlertDescription className="copy-small">Please try again later.</AlertDescription>
          </Alert>
        </div>
      )}

      {!isTooManyRows && isRibbonSlot && (
        <div className="flex min-h-160 items-center justify-center">
          <p className="copy-small text-textSecondary">AI Detections — coming soon.</p>
        </div>
      )}

      {isAiDetectionsSlot && (
        <SiteDetectionsOverviewSection
          siteId={siteId}
          htIds={activeHtIds}
          scopedHydrotwins={scopedHydrotwins}
          startDate={startDate}
          endDate={endDate}
        />
      )}

      {!isTooManyRows && !error && !skipFetch && ChartComponent && (
        <ChartComponent
          seriesData={series}
          scopedHydrotwins={scopedHydrotwins}
          startDate={startDate}
          endDate={endDate}
          isLoading={effectiveLoading}
          emptyMessage={chartEmptyMessage}
          onExtraControls={setExtraControls}
        />
      )}

      {!isTooManyRows && !error && !skipFetch && !ChartComponent && (
        <div className="flex min-h-160 items-center justify-center">
          <p className="copy-small text-textSecondary">Chart not available.</p>
        </div>
      )}
    </ChartCard>
  );
}
