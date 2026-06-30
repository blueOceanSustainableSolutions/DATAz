import { useQuery } from "@tanstack/react-query";
import { fetchSiteDetectionsBinInspection } from "@/api/detections";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

const EMPTY_SERIES = [];

/**
 * Per-htId series of detection events inside a single bin for the Site page.
 * Each event row carries `htId` + `deploymentId` so the beeswarm chart can
 * colour/style it without a second lookup. Cache key sorts htIds.
 */
export function useSiteDetectionsBinInspection(
  siteId,
  htIds,
  binStart,
  binEnd,
  category,
  limit = 200,
) {
  const sortedIds = [...htIds].sort();

  const enabled =
    Boolean(siteId) &&
    sortedIds.length > 0 &&
    Boolean(binStart) &&
    Boolean(binEnd) &&
    Boolean(category);

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "site-detections-bin-inspection",
      siteId,
      sortedIds.join(","),
      binStart,
      binEnd,
      category,
      limit,
    ],
    queryFn: () =>
      fetchSiteDetectionsBinInspection(
        siteId,
        sortedIds,
        binStart,
        binEnd,
        category,
        limit,
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
