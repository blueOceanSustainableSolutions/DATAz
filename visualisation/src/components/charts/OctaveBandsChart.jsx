import { useEffect, useMemo, useRef, useState } from "react";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { siteSplOffset } from "@/lib/charts";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import { OutlineButton, ListItemButton } from "@/components/Buttons";
import { ChevronDown } from "@/components/Icons";

function formatFreq(hz) {
  if (hz >= 1000) {
    const k = hz / 1000;
    return `${k % 1 === 0 ? k : k.toFixed(1)} kHz`;
  }
  return `${hz} Hz`;
}

// spectrum.p50 keys are strings like "40.0", "63.0", etc.
// Try the toFixed(1) form first, then bare string.
function lookupP50(spectrum, hz) {
  const p50 = spectrum?.p50;
  if (!p50) return null;
  return p50[hz.toFixed(1)] ?? p50[String(hz)] ?? p50[hz] ?? null;
}

// Extract sorted numeric frequency bands from a spectrum object.
function extractFreqKeys(spectrum) {
  if (!spectrum?.p50 || typeof spectrum.p50 !== "object") return [];
  return Object.keys(spectrum.p50)
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
}

function BandPicker({ activeHz, availableFreqs, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!availableFreqs.length) return null;

  return (
    <div ref={ref} className="relative">
      <OutlineButton
        size="small"
        onClick={() => setOpen((v) => !v)}
        extraClass="gap-6 whitespace-nowrap"
      >
        Band: {formatFreq(activeHz)}
        <ChevronDown
          extraClass={`transition-transform duration-150 ${open ? "-rotate-180" : ""}`}
        />
      </OutlineButton>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-4 rounded-8 border border-grey300 bg-surface drop-shadow-default"
          style={{ minWidth: 130 }}
        >
          <div className="max-h-240 overflow-y-auto py-4">
            {availableFreqs.map((hz) => {
              const active = activeHz === hz;
              return (
                <ListItemButton
                  key={hz}
                  onClick={() => {
                    onChange(hz);
                    setOpen(false);
                  }}
                >
                  <span
                    className={`copy-extrasmall flex-1 ${active ? "text-primary" : "text-textPrimary"}`}
                  >
                    {formatFreq(hz)}
                  </span>
                  {active && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M2 6l3 3 5-6"
                        stroke="var(--primary)"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </ListItemButton>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function OctaveBandsChart({
  seriesData = [],
  scopedHydrotwins = [],
  isLoading,
  emptyMessage,
  height,
  onExtraControls,
}) {
  const [freqHz, setFreqHz] = useState(null);

  const onExtraControlsRef = useRef(onExtraControls);
  onExtraControlsRef.current = onExtraControls;

  // Frequency bands live inside spectrum.p50's keys, not the spectrum object itself.
  // Union the bands across every selected series so the dropdown reflects the full
  // response — a mixed fleet (e.g. HT-S ~28 bands, HT-C ~33) exposes different sets,
  // and a unit lacking a chosen band simply plots no point there.
  const availableFreqs = useMemo(() => {
    const union = new Set();
    for (const s of seriesData) {
      for (const r of s.readings ?? []) {
        const keys = extractFreqKeys(r.spectrum);
        if (keys.length) {
          keys.forEach((hz) => union.add(hz));
          break; // bands are identical across a series' readings
        }
      }
    }
    return [...union].sort((a, b) => a - b);
  }, [seriesData]);

  // Default to 50 Hz when the response includes it, else the lowest band; an
  // explicit user selection always wins.
  const targetHz = freqHz ?? (availableFreqs.includes(50) ? 50 : (availableFreqs[0] ?? null));

  useEffect(() => {
    onExtraControlsRef.current?.(
      <BandPicker activeHz={targetHz} availableFreqs={availableFreqs} onChange={setFreqHz} />,
    );
  }, [targetHz, availableFreqs]);

  useEffect(() => {
    return () => onExtraControlsRef.current?.(null);
  }, []);

  const series = useMemo(() => {
    if (targetHz == null) return [];

    return seriesData
      .map((s) => {
        // Per-device SPL calibration (HT-S non-6+/003/004 and HT-C need +149.82),
        // mirroring the deployment octave chart so a mixed overlay reads in dB.
        const off = siteSplOffset(s.htId);
        return {
          id: s.htId,
          label: s.htId,
          color: getOverlayColor({ htId: s.htId, scopedHydrotwins }),
          data: s.readings.map((r) => {
            const raw = lookupP50(r.spectrum, targetHz);
            return { t: new Date(r.ingestedAt), v: raw == null ? null : raw + off };
          }),
        };
      })
      // Only plot units that actually report this band — a unit lacking the
      // selected frequency (e.g. HT-S has fewer bands than HT-C) would otherwise
      // render as an empty/straight line and a phantom legend entry.
      .filter((s) => s.data.some((d) => d.v != null && Number.isFinite(d.v)));
  }, [seriesData, scopedHydrotwins, targetHz]);

  return (
    <MultiSeriesLineChart
      series={series}
      yScales={{
        left: {
          label: targetHz != null ? `SPL at ${formatFreq(targetHz)}` : "SPL",
          unit: "dB",
        },
      }}
      isLoading={isLoading}
      emptyMessage={
        availableFreqs.length === 0 && !isLoading
          ? "No spectrum data available."
          : series.length === 0 && availableFreqs.length > 0 && !isLoading
            ? "No unit reports data at this band for the selected range."
            : emptyMessage
      }
      height={height}
    />
  );
}
