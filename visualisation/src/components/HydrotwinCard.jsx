import HydrotwinTypeBadge from "@/components/HydrotwinTypeBadge";
import StatusPill from "@/components/StatusPill";
import SoundLevelGauge from "@/components/SoundLevelGauge";
import DetectionChip from "@/components/DetectionChip";
import SysIndicatorDots from "@/components/SysIndicatorDots";
import { getHydrotwinTypeMeta } from "@/constants/hydrotwinTypeRegistry";
import { calcUsedSDCardGB } from "@/lib/calcUsedSdCardGb";
import { getSDCardCapacityGB } from "@/constants/scoutConfig";

function ChevronIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12 }}>
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}

function fmt(v, decimals, unit) {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(decimals)}${unit ? " " + unit : ""}`;
}

/**
 * HydrotwinCard — matches the design's .hts-card structure.
 *
 * Props:
 *   hydrotwin      HydrotwinDTO   — { htId, type, status, location }
 *   selected       boolean
 *   onClick        () => void
 *   realtimeData   { dB, detections, battery, sdCard, spotter } | null
 *     battery  — 0..1 fraction
 *     sdCard   — 0..1 fill fraction
 *     spotter  — { waveHeight, windSpeed, pressure } | null
 */
export default function HydrotwinCard({
  hydrotwin,
  selected = false,
  onClick,
  onSpotterClick,
  realtimeData,
  hasAcoustics = true,
}) {
  const meta = getHydrotwinTypeMeta(hydrotwin.htId);
  const chips = meta?.defaultDetectionChips ?? ["vessels", "dolphins", "whales"];
  const showSysDots = meta?.hasBatteryStorageStrip ?? false;

  const hasSpotter = Boolean(meta?.hasSpotterPanel);

  const rt = realtimeData ?? {};
  const spotter = rt.hts ?? null;

  const batteryVoltageV = rt.energy?.batteryVoltageV ?? null;
  const latestDeployment = hydrotwin.deployments
    ?.slice()
    .sort((a, b) => new Date(b.deploymentDate ?? b.deployment_date) - new Date(a.deploymentDate ?? a.deployment_date))[0];
  const sdGbUsed = calcUsedSDCardGB(latestDeployment?.deploymentDate ?? latestDeployment?.deployment_date ?? null);
  const sdGbMax = getSDCardCapacityGB(hydrotwin.htId);
  const sdFraction = sdGbUsed != null && sdGbMax > 0 ? sdGbUsed / sdGbMax : null;

  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? "color-mix(in srgb, hsl(var(--primary)) 7%, var(--surface))" : "var(--surface)",
        border: `0.5px solid var(--grey-300)`,
        borderLeft: selected
          ? "3px solid hsl(var(--primary))"
          : "3px solid transparent",
        borderRadius: 10,
        padding: "12px 14px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        position: "relative",
      }}
    >
      {/* Identity strip */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <div style={{ width: 26, height: 26, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <HydrotwinTypeBadge htId={hydrotwin.htId} status={hydrotwin.status} size={26} selected={selected} />
        </div>

        <div style={{ minWidth: 0, overflow: "hidden", flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)", letterSpacing: "-0.01em", marginBottom: 2 }}>
            {hydrotwin.htId}
          </div>
          {hydrotwin.location && (
            <div style={{ fontSize: 11.5, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {hydrotwin.location}
            </div>
          )}
        </div>

        {/* Sys indicator dots — HT-S only, inline in the header row */}
        {showSysDots && (
          <SysIndicatorDots
            batteryVoltageV={batteryVoltageV}
            sdCard={sdFraction}
          />
        )}

        <StatusPill status={hydrotwin.status} size="sm" />
      </div>

      {/* Core strip — noise gauge + detection-prevalence chips. Hidden when the
          site has no acoustic sensors (no acoustic data → no Acoustic tab). */}
      {hasAcoustics && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "6px 0 10px",
          borderTop: "0.5px solid var(--grey-300)",
          borderBottom: "0.5px solid var(--grey-300)",
          marginBottom: 10,
        }}>
          <SoundLevelGauge dB={rt.dB ?? null} width={120} />
          <div style={{ flex: 1, display: "flex", flexDirection: "row", gap: 6, minWidth: 0 }}>
            {chips.map((kind) => (
              <DetectionChip
                key={kind}
                kind={kind}
                activity={rt.detections?.[kind] ?? null}
              />
            ))}
          </div>
        </div>
      )}

      {/* Action strip */}
      <div style={{ display: "flex", alignItems: "center" }}>

        {/* HT-S: metocean mini-stats (when spotter data available) */}
        {hasSpotter && spotter && (
          <div
            onClick={(e) => { e.stopPropagation(); onSpotterClick?.(); }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "8px 12px",
              background: "var(--grey-200)",
              border: "0.5px solid var(--grey-300)",
              borderRadius: 7,
              width: "100%",
              cursor: "pointer",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "var(--text-secondary)", fontSize: 9.5, textTransform: "uppercase", letterSpacing: "0.06em", lineHeight: 1, marginBottom: 2 }}>Wave</div>
              <div style={{ color: "var(--text-primary)", fontWeight: 500, fontSize: 12.5, lineHeight: 1.1 }}>{fmt(spotter.waveHeight, 2, "m")}</div>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "var(--text-secondary)", fontSize: 9.5, textTransform: "uppercase", letterSpacing: "0.06em", lineHeight: 1, marginBottom: 2 }}>Wind</div>
              <div style={{ color: "var(--text-primary)", fontWeight: 500, fontSize: 12.5, lineHeight: 1.1 }}>{fmt(spotter.windSpeed, 1, "kn")}</div>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "var(--text-secondary)", fontSize: 9.5, textTransform: "uppercase", letterSpacing: "0.06em", lineHeight: 1, marginBottom: 2 }}>Pressure</div>
              <div style={{ color: "var(--text-primary)", fontWeight: 500, fontSize: 12.5, lineHeight: 1.1 }}>{fmt(spotter.pressure, 0, "hPa")}</div>
            </div>
            <div style={{ color: "var(--text-secondary)", flexShrink: 0 }}>
              <ChevronIcon />
            </div>
          </div>
        )}

        {/* HT-S without spotter data yet */}
        {hasSpotter && !spotter && (
          <div style={{ fontSize: 11.5, color: "var(--text-secondary)", fontStyle: "italic", paddingLeft: 2 }}>
            No Hydrotwin data
          </div>
        )}
      </div>
    </div>
  );
}
