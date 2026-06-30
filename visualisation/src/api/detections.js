import { API, getJson, iso } from "./http";
import { resolveSiteId } from "./sites";

// GET /api/sites/:id/ai_detections/:metric — one transport for the four variants.
// `series: [{ htId, data }]`; each `data` mirrors the single-hydrotwin shape.
async function fetchSiteAiDetectionsMetric(metric, params) {
  const id = await resolveSiteId();
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null) continue;
    qs.set(k, String(v));
  }
  return getJson(`${API}/sites/${id}/ai_detections/${metric}?${qs}`);
}

export function fetchSiteDetectionsOverview(_siteId, htIds, startDateIso, endDateIso) {
  return fetchSiteAiDetectionsMetric("overview", {
    ht_ids: htIds.join(","),
    start_date: iso(startDateIso),
    end_date: iso(endDateIso),
  });
}

export function fetchSiteDetectionsBins(_siteId, htIds, startDateIso, endDateIso, binMinutes) {
  return fetchSiteAiDetectionsMetric("bins", {
    ht_ids: htIds.join(","),
    start_date: iso(startDateIso),
    end_date: iso(endDateIso),
    bin_minutes: binMinutes,
  });
}

export function fetchSiteDetectionsBinInspection(
  _siteId,
  htIds,
  binStart,
  binEnd,
  category,
  limit = 200,
) {
  return fetchSiteAiDetectionsMetric("bin_inspection", {
    ht_ids: htIds.join(","),
    bin_start: iso(binStart),
    bin_end: iso(binEnd),
    category,
    limit,
  });
}

export function fetchSiteDetectionsRecent(_siteId, htIds, limit = 20) {
  return fetchSiteAiDetectionsMetric("recent", {
    ht_ids: htIds.join(","),
    limit,
  });
}
