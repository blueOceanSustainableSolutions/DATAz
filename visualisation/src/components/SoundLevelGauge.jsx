/**
 * SoundLevelGauge — horizontal bar gauge for broadband SPL.
 *
 * Three colour zones: 0-85 dB green, 85-120 dB amber, 120-150 dB red.
 * A vertical marker indicates the current reading.
 *
 * Props:
 *   dB    number | null   — current broadband SPL (0..150 dB range)
 *   width number          — px width (default 120, matches design)
 */
export default function SoundLevelGauge({ dB, width = 120 }) {
  const MAX = 150;
  const pct = dB != null && Number.isFinite(dB)
    ? `${Math.max(0, Math.min(100, (dB / MAX) * 100)).toFixed(2)}%`
    : null;

  const greenPct = ((85 / MAX) * 100).toFixed(2) + "%";
  const amberPct = (((120 - 85) / MAX) * 100).toFixed(2) + "%";
  const redPct   = (((MAX - 120) / MAX) * 100).toFixed(2) + "%";

  const label = dB != null && Number.isFinite(dB) ? Math.round(dB) : "—";

  return (
    <div style={{ width, flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, paddingTop: 6 }}>
      {/* Segmented track + marker */}
      <div style={{ position: "relative", width: "100%", height: 12 }}>
        <div style={{ display: "flex", width: "100%", height: "100%", borderRadius: 4, overflow: "hidden" }}>
          <div style={{ width: greenPct, height: "100%", background: "color-mix(in srgb, var(--chart-green) 55%, white)" }} />
          <div style={{ width: amberPct, height: "100%", background: "color-mix(in srgb, var(--chart-orange) 55%, white)" }} />
          <div style={{ width: redPct,   height: "100%", background: "color-mix(in srgb, var(--error) 55%, white)" }} />
        </div>
        {pct && (
          <div style={{
            position: "absolute",
            top: -3,
            left: pct,
            width: 3,
            height: 18,
            background: "var(--text-primary)",
            borderRadius: 2,
            transform: "translateX(-50%)",
            boxShadow: "0 0 0 2px var(--surface)",
          }} />
        )}
      </div>

      {/* Value */}
      <div style={{ fontSize: 17, fontWeight: 500, color: "var(--text-primary)", lineHeight: 1, letterSpacing: "-0.01em", marginTop: 2 }}>
        {label}
        {dB != null && <span style={{ fontSize: 11, fontWeight: 400, color: "var(--text-secondary)", marginLeft: 2 }}>dB</span>}
      </div>
      <div style={{ fontSize: 9.5, color: "var(--text-secondary)", letterSpacing: "0.04em", textTransform: "uppercase", marginTop: 1 }}>
        Sound level
      </div>
    </div>
  );
}
