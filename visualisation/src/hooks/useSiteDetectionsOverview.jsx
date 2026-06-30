import { useQuery } from "@tanstack/react-query";
import { fetchSiteDetectionsOverview } from "@/api/detections";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

const EMPTY_SERIES = [];

/**
 * Per-htId series of detection overview aggregates for the Site page.
 * Cache key sorts htIds so order-equivalent calls hit the cache.
 */
export function useSiteDetectionsOverview(siteId, htIds, startDate, endDate) {
  const sortedIds = [...htIds].sort();

  const enabled =
    Boolean(siteId) &&
    sortedIds.length > 0 &&
    Boolean(startDate) &&
    Boolean(endDate);

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "site-detections-overview",
      siteId,
      sortedIds.join(","),
      startDate,
      endDate,
    ],
    queryFn: () =>
      fetchSiteDetectionsOverview(siteId, sortedIds, startDate, endDate),
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
