import { useQuery } from "@tanstack/react-query";
import { getSiteHistoricalSeries } from "@/api/sites";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

const EMPTY_SERIES = [];

/**
 * Fetch bulk historical measurements for a set of hydrotwins at a site.
 *
 * Cache key sorts htIds so that order-equivalent calls always hit the cache.
 * `limit` is part of the key so a cheap availability probe (limit=1) never
 * collides with the full fetch (no limit).
 * Returns `isTooManyRows: true` (and no error) on 422 so the chart can show
 * a non-blocking inline prompt rather than an error state.
 */
export function useSiteHistoricalSeries(siteId, metric, htIds, startDate, endDate, limit) {
  const sortedIds = [...htIds].sort();

  const enabled =
    Boolean(siteId) &&
    Boolean(metric) &&
    sortedIds.length > 0 &&
    Boolean(startDate) &&
    Boolean(endDate);

  const { data, isLoading, error } = useQuery({
    queryKey: ["site", siteId, metric, sortedIds.join(","), startDate, endDate, limit ?? null],
    queryFn: () =>
      getSiteHistoricalSeries(siteId, metric, sortedIds, startDate, endDate, limit),
    enabled,
    ...QUERY_CONFIG,
  });

  const isTooManyRows = error?.code === "too_many_rows";

  return {
    series: data?.series ?? EMPTY_SERIES,
    isLoading,
    error: isTooManyRows ? null : error,
    isTooManyRows,
  };
}
