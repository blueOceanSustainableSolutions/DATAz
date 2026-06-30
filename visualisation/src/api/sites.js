import { API, getJson, iso } from "./http";
import { SITE_ID } from "@/config";

// The backend serves many sites behind `/sites/:id`, but the read-only account
// is scoped to exactly one. Resolve that id once: use VITE_SITE_ID if provided,
// otherwise discover it from the (single-entry) `GET /api/sites` list and cache.
let sitePromise = null;
export function resolveSiteId() {
  if (SITE_ID) return Promise.resolve(String(SITE_ID));
  if (!sitePromise) {
    sitePromise = getJson(`${API}/sites`)
      .then((d) => {
        const id = d?.sites?.[0]?.id;
        if (id == null) throw new Error("This account has no accessible sites.");
        return String(id);
      })
      .catch((e) => {
        sitePromise = null; // allow a later retry
        throw e;
      });
  }
  return sitePromise;
}

// The ported hooks pass a `siteId` for their query keys; the real id is resolved
// here, so that first argument is ignored.

/** GET /api/sites/:id → { site, hydrotwins }. */
export async function getSite() {
  const id = await resolveSiteId();
  return getJson(`${API}/sites/${id}`);
}

/** GET /api/sites/:id/realtime → per-device live snapshot. */
export async function getSiteRealtime() {
  const id = await resolveSiteId();
  return getJson(`${API}/sites/${id}/realtime`);
}

/** GET /api/sites/:id/measurements/:metric. Throws `too_many_rows` on 422. */
export async function getSiteHistoricalSeries(
  _siteId,
  metric,
  htIds,
  startDate,
  endDate,
  limit,
) {
  const id = await resolveSiteId();
  const params = new URLSearchParams({
    ht_ids: htIds.join(","),
    start_date: iso(startDate),
    end_date: iso(endDate),
  });
  if (limit != null) params.set("limit", String(limit));
  return getJson(`${API}/sites/${id}/measurements/${metric}?${params}`);
}
