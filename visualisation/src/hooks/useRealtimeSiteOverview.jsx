import { useQuery } from "@tanstack/react-query";
import { getSiteRealtime } from "@/api/sites";

const REALTIME_POLL_MS = 30_000;

// The backend normally returns prevalence strings ('none'|'low'|'medium'|'high')
// already bucketed by the same thresholds the single-deployment (scout) page
// uses. This numeric fallback only fires if a raw percentage slips through, and
// it MUST use the identical 71/41/>0 cut-offs so the Site and Deployment pages
// label detection activity the same way. See transformNewDetectionsFormat in
// api/hydrotwin/index.js and pctToPrevalence in the backend sites.service.
function pctToActivity(pct) {
  if (pct == null || pct <= 0) return "none";
  if (pct >= 71) return "high";
  if (pct >= 41) return "medium";
  return "low";
}

function normalizeDetections(raw) {
  if (!raw) return null;
  const out = {};
  for (const [key, val] of Object.entries(raw)) {
    out[key] = typeof val === "string" ? val : pctToActivity(val);
  }
  return out;
}

/**
 * useRealtimeSiteOverview — polls GET /api/sites/:siteId/realtime every 30 s.
 *
 * Backend response shape per hydrotwin:
 *   { htId, status, lastActive, dB, detections: {vessels,dolphins,whales} (counts),
 *     battery (0..1 fraction), sdCard (0..1 fraction), signal (0..1),
 *     hts? { waveHeight, windSpeed, pressure, waveDirection, windDirection, wavePeriod },
 *     energy? { batteryVoltageV, solarVoltageV, chargingPowerW },
 *     motion? { speedKn, headingDeg, totalDistM, displacementM, driftRatio, windowHours, positionCount } }
 *
 * Returns:
 *   realtimeByHtId   Map<string, RealtimeSnapshot>
 *   statusCounts     { active, low_battery, charging, unresponsive }
 */
export function useRealtimeSiteOverview(siteId) {
  const { data } = useQuery({
    queryKey: ["site", siteId, "realtime"],
    queryFn: () => getSiteRealtime(siteId).catch(() => null),
    enabled: Boolean(siteId),
    refetchInterval: REALTIME_POLL_MS,
    staleTime: REALTIME_POLL_MS,
    throwOnError: false,
  });

  const realtimeByHtId = new Map();
  const trailsByHtId = new Map();
  const statusCounts = { active: 0, low_battery: 0, charging: 0, unresponsive: 0, maintenance: 0, decommissioned: 0 };

  if (data?.hydrotwins) {
    for (const ht of data.hydrotwins) {
      realtimeByHtId.set(ht.htId, {
        dB:         ht.dB ?? null,
        detections: normalizeDetections(ht.detections),
        battery:    ht.battery ?? null,
        sdCard:     ht.sdCard ?? null,
        hts:        ht.hts ?? null,
        energy:     ht.energy ?? null,
        motion:     ht.motion ?? null,
      });
      // Movement trail ({ lng, lat, t } points) — HT-S (drift) / HT-V (track); absent for HT-C.
      if (ht.trail?.length) trailsByHtId.set(ht.htId, ht.trail);
      const key = ht.status?.toLowerCase?.().replace(/-/g, "_");
      if (key in statusCounts) statusCounts[key]++;
    }
  }

  return { realtimeByHtId, trailsByHtId, statusCounts };
}
