import { useState } from "react";
import SiteHeader from "@/components/SiteHeader";
import SiteMap from "@/components/SiteMap";
import HydrotwinRail from "@/components/HydrotwinRail";
import SiteTabbedAnalysis from "@/components/SiteTabbedAnalysis";
import SpotterDetailsModal from "@/components/SpotterDetailsModal";
import { useSiteWithHydrotwins } from "@/hooks/useSiteWithHydrotwins";
import { useRealtimeSiteOverview } from "@/hooks/useRealtimeSiteOverview";
import { useSiteTabOrchestrator } from "@/hooks/useSiteTabOrchestrator";
import { PAGE_TITLE } from "@/config";

// The open backend serves one fixed site, so there is no id in the URL. The
// ported hooks still take a `siteId` for their React-Query keys / enabled flags,
// so we hand them a stable constant.
const SITE_KEY = "site";

function defaultDateRange() {
  // "Today only": start of today UTC → now, matching the source default.
  const end = new Date();
  const start = new Date(end);
  start.setUTCHours(0, 0, 0, 0);
  return { start: start.toISOString(), end: end.toISOString() };
}

export default function App() {
  const { hydrotwins, isLoading, error } = useSiteWithHydrotwins(SITE_KEY);

  const [{ start: startDate, end: endDate }, setDateRange] = useState(defaultDateRange);
  const [selectedHtId, setSelectedHtId] = useState(null);
  const [spotterHtId, setSpotterHtId] = useState(null);

  const { realtimeByHtId, trailsByHtId, statusCounts } = useRealtimeSiteOverview(SITE_KEY);

  const handleDatesApply = (from, to) => {
    setDateRange({
      start: from instanceof Date ? from.toISOString() : from,
      end: to instanceof Date ? to.toISOString() : to,
    });
  };

  // Shared probe drives the visible tabs AND whether rail cards show acoustic readouts.
  const orchestrator = useSiteTabOrchestrator({
    siteId: SITE_KEY,
    hydrotwins,
    startDate,
    endDate,
  });
  const hasAcoustics =
    orchestrator.isProbing || orchestrator.tabs.some((t) => t.id === "acoustic");

  if (error && !isLoading) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--app-background)" }}>
        <div
          style={{ maxWidth: 1600, margin: "0 auto" }}
          className="flex min-h-[60vh] items-center justify-center px-16 py-40 768:px-32"
        >
          <p className="copy-body text-textSecondary text-center">
            We couldn&apos;t load this site. Please refresh or try again later.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--app-background)" }}>
      <div style={{ maxWidth: 1600, margin: "0 auto" }} className="px-16 pb-40 768:px-32">
        <SiteHeader title={PAGE_TITLE} statusCounts={statusCounts} />

        {/* Map + Rail — stacks vertically on mobile, 56%/1fr grid at 768+ */}
        <div className="mb-14 grid grid-cols-1 gap-14 768:grid-cols-[56%_1fr]">
          <div
            className="h-[420px] 768:h-[640px]"
            style={{
              background: "var(--surface)",
              borderRadius: 12,
              border: "0.5px solid var(--grey-300)",
              position: "relative",
              overflow: "hidden",
              isolation: "isolate",
            }}
          >
            <SiteMap
              hydrotwins={hydrotwins}
              selectedHtId={selectedHtId}
              onHydrotwinClick={setSelectedHtId}
              trailsByHtId={trailsByHtId}
            />
          </div>

          <div
            className="h-[280px] 768:h-[640px]"
            style={{
              background: "var(--surface)",
              borderRadius: 12,
              border: "0.5px solid var(--grey-300)",
              position: "relative",
              overflow: "hidden",
              padding: 12,
            }}
          >
            <HydrotwinRail
              hydrotwins={hydrotwins}
              isLoading={isLoading}
              selectedHtId={selectedHtId}
              onSelect={setSelectedHtId}
              onSpotterClick={setSpotterHtId}
              realtimeByHtId={realtimeByHtId}
              hasAcoustics={hasAcoustics}
            />
          </div>
        </div>

        <SiteTabbedAnalysis
          orchestrator={orchestrator}
          siteId={SITE_KEY}
          hydrotwins={hydrotwins}
          isLoading={isLoading}
          startDate={startDate}
          endDate={endDate}
          handleDatesApply={handleDatesApply}
        />

        <SpotterDetailsModal
          hydrotwin={
            spotterHtId ? hydrotwins.find((h) => h.htId === spotterHtId) ?? null : null
          }
          realtimeData={spotterHtId ? realtimeByHtId?.get(spotterHtId) ?? null : null}
          onClose={() => setSpotterHtId(null)}
        />
      </div>
    </div>
  );
}
