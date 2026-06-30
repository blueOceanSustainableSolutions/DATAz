import { useQuery } from "@tanstack/react-query";
import { fetchSiteDetectionsBins } from "@/api/detections";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

const EMPTY_SERIES = [];

/**
 * Per-htId series of binned detection aggregates (heatmap) for the Site page.
 * Backend guarantees every series uses the same effective bin grid so the
 * frontend can fold them on a common axis. Cache key sorts htIds.
 */
export function useSiteDetectionsBins(
  siteId,
  htIds,
  startDate,
  endDate,
  binMinutes,
) {
  const sortedIds = [...htIds].sort();

  const enabled =
    Boolean(siteId) &&
    sortedIds.length > 0 &&
    Boolean(startDate) &&
    Boolean(endDate) &&
    Boolean(binMinutes);

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "site-detections-bins",
      siteId,
      sortedIds.join(","),
      startDate,
      endDate,
      binMinutes,
    ],
    queryFn: () =>
      fetchSiteDetectionsBins(
        siteId,
        sortedIds,
        startDate,
        endDate,
        binMinutes,
      ),
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
