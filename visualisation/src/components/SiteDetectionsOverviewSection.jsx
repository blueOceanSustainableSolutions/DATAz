"use client";

import { useCallback, useMemo, useState } from "react";
import { useSiteDetectionsOverview } from "@/hooks/useSiteDetectionsOverview";
import { foldOverviewSeries } from "@/lib/siteDetections";
import {
  detectionsStartIso,
  detectionsEndIso,
  rangeIncludesToday,
} from "@/lib/detections";
import OverviewStatsCard from "@/components/OverviewStatsCard";
import RecentDetectionsCard from "@/components/RecentDetectionsCard";
import BinnedAggregatesCard from "@/components/BinnedAggregatesCard";
import BinInspectionModal from "@/components/BinInspectionModal";

/**
 * AI Detections section for the Site page (multi-deployment).
 *
 * Mirrors DetectionsOverviewSection but fetches from /api/sites/.../ai_detections/*
 * and folds the per-htId series through siteDetections.js. Each child card
 * receives a `siteContext` prop so it sources its own data from the Site
 * endpoints. The BinInspectionModal gets `multiDeployment={true}` so it renders
 * the beeswarm + deployment legend in place of the single-event strip chart.
 */
export default function SiteDetectionsOverviewSection({
  siteId,
  htIds,
  scopedHydrotwins,
  startDate,
  endDate,
}) {
  const startIso = useMemo(
    () => (startDate ? detectionsStartIso(startDate) : null),
    [startDate],
  );
  const endIso = useMemo(
    () => (endDate ? detectionsEndIso(endDate) : null),
    [endDate],
  );

  const includesToday = useMemo(
    () => Boolean(endIso) && rangeIncludesToday(endIso),
    [endIso],
  );

  // ── Overview data ────────────────────────────────────────────────────────
  const {
    series: overviewSeries,
    isLoading,
    error,
  } = useSiteDetectionsOverview(siteId, htIds, startIso, endIso);

  const overview = useMemo(
    () => (overviewSeries.length > 0 ? foldOverviewSeries(overviewSeries) : null),
    [overviewSeries],
  );

  // ── siteContext passed to child cards + modal ────────────────────────────
  const siteContext = useMemo(
    () => ({ siteId, htIds, scopedHydrotwins }),
    [siteId, htIds, scopedHydrotwins],
  );

  // ── Modal state ──────────────────────────────────────────────────────────
  const [modalParams, setModalParams] = useState(null);
  const isModalOpen = Boolean(modalParams);

  const handleOpenBinInspection = useCallback((params) => {
    setModalParams(params);
  }, []);

  const handleCloseModal = useCallback(() => {
    setModalParams(null);
  }, []);

  if (!siteId || htIds.length === 0) {
    return (
      <div className="flex min-h-160 items-center justify-center">
        <p className="copy-small text-textSecondary">
          Select at least one hydrotwin to show AI detections.
        </p>
      </div>
    );
  }

  return (
    <div className="col-span-12">
      <div className="overflow-hidden rounded-[10px] border border-grey200 bg-surface shadow-[1px_2px_4px_rgba(0,0,0,0.12)] [&>*:last-child]:border-b-0">
        <OverviewStatsCard
          overview={overview}
          isLoading={isLoading}
          error={error}
        />
        <BinnedAggregatesCard
          startIso={startIso}
          endIso={endIso}
          overviewIntervalMinutes={overview?.intervalMinutes}
          onOpenBinInspection={handleOpenBinInspection}
          siteContext={siteContext}
        />
        {includesToday && (
          <RecentDetectionsCard
            onOpenBinInspection={handleOpenBinInspection}
            siteContext={siteContext}
          />
        )}
      </div>

      {/* Single modal instance — opened by either the heatmap or the recent table */}
      {modalParams && (
        <BinInspectionModal
          isOpen={isModalOpen}
          onClose={handleCloseModal}
          classId={modalParams.classId}
          classColor={modalParams.classColor}
          binStart={modalParams.binStart}
          binEnd={modalParams.binEnd}
          binMinutes={modalParams.binMinutes}
          binsForNavigation={modalParams.binsForNavigation ?? []}
          focused={modalParams.focused ?? false}
          pinnedEventAt={modalParams.pinnedEventAt ?? null}
          siteContext={siteContext}
          multiDeployment
        />
      )}
    </div>
  );
}
