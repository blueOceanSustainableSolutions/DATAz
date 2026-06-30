import { useQuery } from "@tanstack/react-query";
import { getSite } from "@/api/sites";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

export function useSiteWithHydrotwins(siteId) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["site", siteId],
    queryFn: () => getSite(siteId),
    enabled: Boolean(siteId),
    ...QUERY_CONFIG,
  });

  return {
    site: data?.site ?? null,
    hydrotwins: data?.hydrotwins ?? [],
    isLoading,
    error,
  };
}
