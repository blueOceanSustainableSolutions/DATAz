import { useQueries } from "@tanstack/react-query";
import { getSiteHistoricalSeries } from "@/api/sites";
import { QUERY_CONFIG } from "@/hooks/queryConfig";
import {
  SITE_MEASUREMENT_METRICS,
  SITE_CHART_CARDS,
} from "@/constants/siteChartCards";
import { hydrotwinParticipatesIn } from "@/constants/hydrotwinTypeRegistry";

// metric -> the card ids backed by it. A hydrotwin contributes to a metric's
// probe when it participates in any card using that metric.
const METRIC_CARD_IDS = (() => {
  const map = {};
  for (const cards of Object.values(SITE_CHART_CARDS)) {
    for (const c of cards) {
      if (!c.metric) continue;
      (map[c.metric] ??= []).push(c.id);
    }
  }
  return map;
})();

// One row per hydrotwin is enough to learn "does this metric have data in the
// range?" — and the backend's 422 row-guard (htCount * limit) can never trip at
// limit=1, so the probe is always safe regardless of range width.
const PROBE_LIMIT = 1;

/**
 * Cheap per-graph data-availability probe for a site's fleet over a date range.
 *
 * Fans out a `limit=1` query per measurement metric (metrics are shared across
 * graphs, so this is ~9 tiny requests regardless of graph count). Returns, per
 * metric, the set of hydrotwins that actually have data — the signal the
 * orchestrator rolls up into tab/graph visibility. Probe results are cached by
 * React Query and never collide with the full chart fetches (the limit is part
 * of the query key).
 *
 * The AI Detections slot is intentionally not probed here: it owns a rich
 * self-contained empty/loading/error UI and is shown whenever applicable.
 *
 * @returns {{
 *   byMetric: Record<string, { isLoading: boolean, isError: boolean, htIdsWithData: Set<string> }>,
 *   isProbing: boolean,
 * }}
 */
export function useSiteGraphAvailability({ siteId, hydrotwins, startDate, endDate }) {
  // Per-metric participating htIds (by hydrotwin type).
  const metricHtIds = SITE_MEASUREMENT_METRICS.map((metric) => {
    const cardIds = METRIC_CARD_IDS[metric] ?? [];
    return hydrotwins
      .filter((h) => cardIds.some((cid) => hydrotwinParticipatesIn(h.htId, cid)))
      .map((h) => h.htId);
  });

  const probes = useQueries({
    queries: SITE_MEASUREMENT_METRICS.map((metric, i) => {
      const sortedIds = [...metricHtIds[i]].sort();
      return {
        queryKey: ["site", siteId, metric, sortedIds.join(","), startDate, endDate, PROBE_LIMIT],
        queryFn: () =>
          getSiteHistoricalSeries(siteId, metric, sortedIds, startDate, endDate, PROBE_LIMIT),
        enabled:
          Boolean(siteId) && sortedIds.length > 0 && Boolean(startDate) && Boolean(endDate),
        ...QUERY_CONFIG,
      };
    }),
  });

  const byMetric = {};
  SITE_MEASUREMENT_METRICS.forEach((metric, i) => {
    const q = probes[i];
    byMetric[metric] = {
      isLoading: q.isLoading,
      isError: Boolean(q.error),
      htIdsWithData: new Set(
        (q.data?.series ?? [])
          .filter((s) => (s.count ?? 0) > 0)
          .map((s) => s.htId),
      ),
    };
  });

  const isProbing = probes.some((q) => q.isLoading);

  return { byMetric, isProbing };
}
