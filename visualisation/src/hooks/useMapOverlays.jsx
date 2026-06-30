import { useQuery } from "@tanstack/react-query";
import {
  fetchMapOverlays,
  fetchMapOverlayManifest,
} from "@/api/map-overlays";
import { QUERY_CONFIG } from "@/hooks/queryConfig";

const EMPTY = [];

/**
 * List of available map overlays (one per simulator variable). Cheap summaries —
 * the heavy per-frame manifest is fetched separately once a result is selected.
 */
export function useMapOverlays(enabled = true) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["map-overlays"],
    queryFn: fetchMapOverlays,
    enabled,
    ...QUERY_CONFIG,
  });

  return { results: data ?? EMPTY, isLoading, error };
}

/**
 * One overlay's manifest (frames + bbox + color scale + Blob base URL + SAS token).
 * Cached per id; the SAS token inside stays valid for its lifetime (~hours).
 */
export function useMapOverlayManifest(id) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["map-overlay-manifest", id],
    queryFn: () => fetchMapOverlayManifest(id),
    enabled: Boolean(id),
    ...QUERY_CONFIG,
  });

  return { manifest: data ?? null, isLoading, error };
}
