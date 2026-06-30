import HydrotwinTypeBadge from "@/components/HydrotwinTypeBadge";
import StatusPill from "@/components/StatusPill";
import { formatDistance } from "@/lib/geo";
import { calcUsedSDCardGB } from "@/lib/calcUsedSdCardGb";
import { getSDCardCapacityGB } from "@/constants/scoutConfig";

function fmt(v, decimals, unit) {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(decimals)}${unit ? " " + unit : ""}`;
}

function fmtDir(deg) {
  if (deg == null || !Number.isFinite(deg)) return "—";
  const d = ((deg % 360) + 360) % 360;
  const cardinals = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  const cardinal = cardinals[Math.round(d / 22.5) % 16];
  return `${Math.round(d)}° ${cardinal}`;
}

function getLevelByVoltage(v) {
  if (v == null || !Number.isFinite(v)) return null;
  if (v >= 4) return 4;
  if (v >= 3.7) return 3;
  if (v >= 3.4) return 2;
  return 1;
}

function IndicatorDots({ value, total = 4, color = "var(--chart-green)" }) {
  if (value == null) return <span style={{ color: "var(--text-secondary)" }}>—</span>;
  return (
    <span style={{ display: "inline-flex", gap: 3 }}>
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: i < value ? color : "var(--grey-300)",
            display: "inline-block",
          }}
        />
      ))}
    </span>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <div style={{ padding: "18px 24px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{title}</span>
        {subtitle && <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>· {subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

function DataGrid({ rows }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px" }}>
      {rows.map(({ label, value }) => (
        <div key={label}>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 2, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

function Divider() {
  return <div style={{ height: "0.5px", background: "var(--grey-300)", margin: "0 24px" }} />;
}

/**
 * SpotterDetailsModal — slide-over panel for HT-S spotter + system data.
 *
 * Props:
 *   hydrotwin    HydrotwinDTO | null
 *   realtimeData { dB, detections, battery, sdCard, hts, energy, motion } | null
 *   onClose      () => void
 */
export default function SpotterDetailsModal({ hydrotwin, realtimeData, onClose }) {
  if (!hydrotwin) return null;

  const rt     = realtimeData ?? {};
  const hts    = rt.hts ?? null;
  const energy = rt.energy ?? null;
  const motion = rt.motion ?? null;

  const batteryLevel = getLevelByVoltage(energy?.batteryVoltageV);
  const batteryColor = !batteryLevel || batteryLevel <= 1 ? "var(--error)" : batteryLevel === 2 ? "var(--chart-orange)" : "var(--chart-green)";

  const latestDeployment = hydrotwin.deployments
    ?.slice()
    .sort((a, b) => new Date(b.deploymentDate ?? b.deployment_date) - new Date(a.deploymentDate ?? a.deployment_date))[0];
  const sdGbUsed = calcUsedSDCardGB(latestDeployment?.deploymentDate ?? latestDeployment?.deployment_date ?? null);
  const sdGbMax  = getSDCardCapacityGB(hydrotwin.htId);
  const sdFraction = sdGbUsed != null && sdGbMax > 0 ? sdGbUsed / sdGbMax : null;
  const sdLevel    = sdFraction != null ? Math.min(4, Math.ceil(sdFraction * 4)) : null;
  const sdColor    = sdFraction != null && sdFraction >= 0.75 ? "var(--error)" : "var(--chart-green)";

  const htsRows = [
    { label: "Wave Height",    value: fmt(hts?.waveHeight, 2, "m") },
    { label: "Wind Speed",     value: fmt(hts?.windSpeed, 1, "kn") },
    { label: "Wave Direction", value: fmtDir(hts?.waveDirection) },
    { label: "Wind Direction", value: fmtDir(hts?.windDirection) },
    { label: "Wave Period",    value: fmt(hts?.wavePeriod, 1, "s") },
    { label: "Pressure",       value: fmt(hts?.pressure, 0, "hPa") },
  ];

  const motionRows = [
    { label: "Speed",          value: fmt(motion?.speedKn, 2, "kn") },
    { label: "Heading",        value: fmtDir(motion?.headingDeg) },
    { label: "Total distance", value: formatDistance(motion?.totalDistM) },
    { label: "Displacement",   value: formatDistance(motion?.displacementM) },
    { label: "Drift ratio",    value: motion?.driftRatio != null ? motion.driftRatio.toFixed(2) : "—" },
  ];

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 500 }}
      />

      {/* Panel */}
      <div style={{
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: 680,
        maxWidth: "calc(100vw - 32px)",
        maxHeight: "calc(100vh - 80px)",
        overflowY: "auto",
        background: "var(--surface)",
        borderRadius: 14,
        border: "0.5px solid var(--grey-300)",
        boxShadow: "0 24px 64px rgba(0,0,0,0.35)",
        zIndex: 501,
      }}>
        {/* Header */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "20px 24px",
          borderBottom: "0.5px solid var(--grey-300)",
        }}>
          <HydrotwinTypeBadge htId={hydrotwin.htId} status={hydrotwin.status} size={36} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 17, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
              {hydrotwin.htId}
            </div>
            {hydrotwin.location && (
              <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginTop: 2 }}>
                {hydrotwin.location}
              </div>
            )}
          </div>
          <StatusPill status={hydrotwin.status} />
          <button
            onClick={onClose}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 30, height: 30, borderRadius: 8,
              border: "0.5px solid var(--grey-300)", background: "var(--grey-200)",
              color: "var(--text-secondary)", cursor: "pointer",
              fontFamily: "inherit", fontSize: 16, lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* HTS data */}
        <Section title="HTS Data" subtitle="latest reading">
          <DataGrid rows={htsRows} />
        </Section>

        <Divider />

        {/* Motion */}
        <Section title="Motion" subtitle={motion?.windowHours ? `last ${motion.windowHours}h` : undefined}>
          <DataGrid rows={motionRows} />
        </Section>

        <Divider />

        {/* Storage */}
        <Section title="Storage (estimated)">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ width: 20, height: 20, color: "var(--text-secondary)", flexShrink: 0 }}>
              <rect x="2" y="6" width="20" height="12" rx="2" />
              <path d="M6 12h.01M10 12h.01" />
            </svg>
            <span style={{ fontSize: 13, color: "var(--text-primary)", flex: 1 }}>Estimated SD Card Usage</span>
            <IndicatorDots value={sdLevel} color={sdColor} />
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", minWidth: 60, textAlign: "right" }}>
              {sdGbUsed != null ? `${sdGbUsed}/${sdGbMax} GB` : "—"}
            </span>
          </div>
        </Section>

        <Divider />

        {/* Energy & Battery */}
        <Section title="Energy & Battery">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ width: 20, height: 20, color: "var(--text-secondary)", flexShrink: 0 }}>
                <rect x="2" y="7" width="18" height="10" rx="2" />
                <path d="M22 11v2" strokeLinecap="round" />
              </svg>
              <span style={{ fontSize: 13, color: "var(--text-primary)", flex: 1 }}>Battery Voltage</span>
              <IndicatorDots value={batteryLevel} color={batteryColor} />
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", minWidth: 60, textAlign: "right" }}>
                {energy?.batteryVoltageV != null ? `${energy.batteryVoltageV.toFixed(1)} V` : "—"}
              </span>
            </div>


            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ width: 20, height: 20, color: "var(--text-secondary)", flexShrink: 0 }}>
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
              </svg>
              <span style={{ fontSize: 13, color: "var(--text-primary)", flex: 1 }}>Solar Voltage</span>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                {energy?.solarVoltageV != null ? `${energy.solarVoltageV.toFixed(1)} V` : "—"}
              </span>
            </div>
          </div>
        </Section>
      </div>
    </>
  );
}
