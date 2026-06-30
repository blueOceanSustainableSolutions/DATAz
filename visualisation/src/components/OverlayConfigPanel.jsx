import { useMemo } from "react";
import CustomSelect from "@/components/CustomSelect";
import SegmentedToggle from "@/components/SegmentedToggle";
import { CloseIcon } from "@/components/Icons";
import {
  OVERLAY_BASEMAP_OPTIONS,
  OVERLAY_FPS_OPTIONS,
  overlayGradientCss,
  buildStepOptions,
} from "@/constants/numericalOverlay";

/** Section wrapper matching the dashboard rail's titled blocks. */
function PanelSection({ title, children }) {
  return (
    <section className="border-b border-grey300 py-14 last:border-0">
      <h3 className="copy-extrasmall mb-10 font-semibold uppercase tracking-wide text-grey500">
        {title}
      </h3>
      {children}
    </section>
  );
}

/**
 * OverlayConfigPanel — slide-in configuration rail (right side of the map).
 *
 * Holds the "what am I looking at" controls — dataset, variable, basemap, opacity — so
 * the map stays the focus and playback lives at the bottom. Styled like the dashboard's
 * detail rail: glyph-free header, titled sections, close button. Hidden by default; the
 * parent toggles `open`.
 *
 * Props use {key,label}/{id,label} option lists so the underlying string-based
 * CustomSelect maps cleanly back to ids on change.
 */
export default function OverlayConfigPanel({
  open,
  onClose,
  datasets = [],
  selectedDatasetKey,
  onSelectDataset,
  variables = [],
  selectedVariableId,
  onSelectVariable,
  basemap,
  onBasemap,
  opacity,
  onOpacity,
  manifest,
  colorScale,
  variable,
  player,
}) {
  const datasetLabels = datasets.map((d) => d.label);
  const selectedDatasetLabel =
    datasets.find((d) => d.key === selectedDatasetKey)?.label ?? null;

  const variableLabels = variables.map((v) => v.label);
  const selectedVariableLabel =
    variables.find((v) => v.id === selectedVariableId)?.label ?? null;

  const fpsLabels = OVERLAY_FPS_OPTIONS.map((f) => `${f} fps`);
  const stepOptions = useMemo(
    () => buildStepOptions(player?.intervalSeconds),
    [player?.intervalSeconds],
  );
  const stepLabels = stepOptions.map((s) => s.label);
  const stepLabel =
    stepOptions.find((s) => s.value === player?.step)?.label ?? stepOptions[0]?.label;

  return (
    <aside
      aria-label="Visualization configuration"
      aria-hidden={!open}
      className={`absolute right-0 top-0 z-[450] flex h-full w-[300px] max-w-[88%] flex-col border-l border-grey300 bg-surface shadow-lg transition-transform duration-300 ${
        open ? "translate-x-0" : "pointer-events-none translate-x-full"
      }`}
    >
      <header className="flex shrink-0 items-center justify-between border-b border-grey300 px-16 py-14">
        <div className="flex min-w-0 flex-col gap-2">
          <span className="copy-small font-bold text-textPrimary">Visualization</span>
          {manifest && (
            <span className="copy-extrasmall truncate text-grey500">
              {manifest.simulator?.toUpperCase()} · {manifest.time?.count} frames
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Hide configuration"
          className="shrink-0 text-grey500 transition-colors media-hover:hover:text-textPrimary"
        >
          <CloseIcon extraClass="w-18 h-18" />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-16">
        {colorScale && (() => {
          const { vmin, vmax, colormap, mode } = colorScale;
          const perFrame = mode === "per-frame" || vmin == null || vmax == null;
          const fmt = (n) => (Number.isInteger(n) ? n : Number(n).toFixed(1));
          const isDirection =
            (variable?.units || "").toLowerCase().startsWith("degree") &&
            vmin === 0 && vmax === 360;
          const ticks = perFrame ? [] : isDirection ? [0, 90, 180, 270, 360] : [vmin, (vmin + vmax) / 2, vmax];
          return (
            <PanelSection title="Colour scale">
              <p className="copy-extrasmall mb-8 text-textPrimary">
                {variable?.long_name || variable?.name || "value"}
                {variable?.units && (
                  <span className="text-grey500"> ({variable.units})</span>
                )}
              </p>
              <div
                className="h-8 w-full rounded-4"
                style={{ background: overlayGradientCss(colormap) }}
              />
              <div className="mt-6 flex justify-between">
                {perFrame ? (
                  <span className="copy-extrasmall text-grey500">per-frame auto-stretch</span>
                ) : (
                  ticks.map((t, i) => (
                    <span key={i} className="copy-extrasmall text-grey500">{fmt(t)}</span>
                  ))
                )}
              </div>
              {!perFrame && isDirection && (
                <p className="mt-2 copy-extrasmall text-grey400">cyclic 0–360°</p>
              )}
            </PanelSection>
          );
        })()}

        <PanelSection title="Dataset">
          <CustomSelect
            placeholder="Select dataset"
            hasOptionsTitle={false}
            searchable={datasetLabels.length > 6}
            options={datasetLabels}
            selectedOption={selectedDatasetLabel}
            setSelectedOption={(label) => {
              const d = datasets.find((x) => x.label === label);
              if (d) onSelectDataset(d.key);
            }}
          />
        </PanelSection>

        {variables.length > 1 && (
          <PanelSection title="Variable">
            <CustomSelect
              placeholder="Select variable"
              hasOptionsTitle={false}
              options={variableLabels}
              selectedOption={selectedVariableLabel}
              setSelectedOption={(label) => {
                const v = variables.find((x) => x.label === label);
                if (v) onSelectVariable(v.id);
              }}
            />
          </PanelSection>
        )}

        {player && (
          <PanelSection title="Playback speed">
            <CustomSelect
              hasOptionsTitle={false}
              options={fpsLabels}
              selectedOption={`${player.fps} fps`}
              setSelectedOption={(label) =>
                player.setFps(Number(String(label).replace(" fps", "")))
              }
            />
          </PanelSection>
        )}

        {player && (
          <PanelSection title="Time step">
            <CustomSelect
              hasOptionsTitle={false}
              options={stepLabels}
              selectedOption={stepLabel}
              setSelectedOption={(label) => {
                const opt = stepOptions.find((s) => s.label === label);
                if (opt) player.setStep(opt.value);
              }}
            />
          </PanelSection>
        )}

        <PanelSection title="Basemap">
          <SegmentedToggle
            ariaLabel="Basemap style"
            options={OVERLAY_BASEMAP_OPTIONS}
            value={basemap}
            onChange={onBasemap}
          />
        </PanelSection>

        <PanelSection title="Overlay opacity">
          <div className="flex items-center gap-12">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => onOpacity(Number(e.target.value))}
              aria-label="Overlay opacity"
              className="h-4 w-full cursor-pointer appearance-none rounded-full bg-grey300 accent-primary"
            />
            <span className="copy-small w-[40px] shrink-0 text-right tabular-nums text-textSecondary">
              {Math.round(opacity * 100)}%
            </span>
          </div>
        </PanelSection>
      </div>
    </aside>
  );
}
