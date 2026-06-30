/**
 * SysIndicatorDots — inline battery + SD card dots for HT-S cards.
 * Matches the .hts-card-sys-inline / .hts-sys-item design.
 *
 * Props:
 *   batteryVoltageV  number | null   — raw battery voltage (V); level derived via getLevelByVoltage
 *   sdCard           number | null   — SD fill fraction 0..1; computed from deployment date upstream
 */

function BatteryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13, flexShrink: 0 }}>
      <rect x="2" y="7" width="18" height="10" rx="2" />
      <path d="M22 11v2" />
      <path d="M5 10v4" strokeWidth="3" />
      <path d="M9 10v4" strokeWidth="3" />
    </svg>
  );
}

function SdIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13, flexShrink: 0 }}>
      <path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
      <path d="M10 5v3M13 5v3M16 5v3" />
    </svg>
  );
}

function Dot({ cls }) {
  const colors = {
    ok:    "var(--chart-green)",
    warn:  "var(--chart-orange)",
    bad:   "var(--error)",
    empty: "var(--grey-400, #b5b8b8)",
  };
  return (
    <div style={{
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: colors[cls] ?? colors.empty,
    }} />
  );
}

function getLevelByVoltage(v) {
  if (v >= 4) return 4;
  if (v >= 3.7) return 3;
  if (v >= 3.4) return 2;
  return 1;
}

// batteryVoltageV → 0-4 dots
function batteryDots(voltageV) {
  const level = getLevelByVoltage(voltageV);
  const cls = level <= 1 ? "bad" : level === 2 ? "warn" : "ok";
  return Array.from({ length: 4 }, (_, i) => (
    <Dot key={i} cls={i < level ? cls : "empty"} />
  ));
}

// sdCard: 0..1 fill fraction → 0-4 dots
function storageDots(fraction) {
  const level = fraction >= 1 ? 4 : Math.min(3, Math.floor(fraction * 4));
  const cls = fraction >= 1 ? "bad" : fraction >= 0.75 ? "warn" : "ok";
  return Array.from({ length: 4 }, (_, i) => (
    <Dot key={i} cls={i < level ? cls : "empty"} />
  ));
}

export default function SysIndicatorDots({ batteryVoltageV, sdCard }) {
  const hasBattery = batteryVoltageV != null && Number.isFinite(batteryVoltageV);
  const hasStorage = sdCard != null && Number.isFinite(sdCard);

  if (!hasBattery && !hasStorage) return null;

  const itemStyle = {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    color: "var(--text-primary)",
  };
  const dotsStyle = {
    display: "inline-flex",
    gap: 3,
  };

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 10, marginLeft: "auto", flexShrink: 0 }}>
      {hasBattery && (
        <div style={itemStyle} title={`Battery: ${batteryVoltageV.toFixed(1)} V`}>
          <BatteryIcon />
          <div style={dotsStyle}>{batteryDots(batteryVoltageV)}</div>
        </div>
      )}
      {hasStorage && (
        <div style={itemStyle} title={`Storage: ${Math.round(sdCard * 100)}% used`}>
          <SdIcon />
          <div style={dotsStyle}>{storageDots(sdCard)}</div>
        </div>
      )}
    </div>
  );
}
