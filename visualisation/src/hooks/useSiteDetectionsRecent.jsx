import { useQuery } from "@tanstack/react-query";
import { fetchSiteDetectionsRecent } from "@/api/detections";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

const EMPTY_SERIES = [];
const RECENT_REFETCH_MS = 60 * 1000;

/**
 * Per-htId series of recent detections (last 24h) for the Site page.
 * Polls every 60s to match the Scout RecentDetectionsCard cadence.
 * Cache key sorts htIds.
 */
export function useSiteDetectionsRecent(siteId, htIds, limit = 20) {
  const sortedIds = [...htIds].sort();

  const enabled = Boolean(siteId) && sortedIds.length > 0;

  const { data, isLoading, error } = useQuery({
    queryKey: ["site-detections-recent", siteId, sortedIds.join(","), limit],
    queryFn: () => fetchSiteDetectionsRecent(siteId, sortedIds, limit),
    enabled,
    refetchInterval: RECENT_REFETCH_MS,
    refetchIntervalInBackground: false,
    ...QUERY_CONFIG,
  });

  return {
    series: data?.series ?? EMPTY_SERIES,
    isLoading,
    error,
  };
}
