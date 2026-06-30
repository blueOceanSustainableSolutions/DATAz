import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "@/context/ThemeProvider";
import Spinner from "@/components/Spinner";
import OverlayColorbar from "@/components/OverlayColorbar";
import { ControlPanelIcon, FitToFleetIcon } from "@/components/Icons";
import OverlayRasterMap from "@/components/OverlayRasterMap";
import OverlayConfigPanel from "@/components/OverlayConfigPanel";
import OverlayPlaybackBar from "@/components/OverlayPlaybackBar";
import { useMapOverlays, useMapOverlayManifest } from "@/hooks/useMapOverlays";
import { useOverlayPlayer } from "@/hooks/useOverlayPlayer";
import { overlayFrameUrl } from "@/api/map-overlays";
import {
  OVERLAY_BASEMAPS,
  overlayDatasetKey,
  overlayDatasetLabel,
  overlayVariableLabel,
} from "@/constants/numericalOverlay";

/** Small floating map toolbar button (top-left), matching SiteMap's control chips. */
function MapToolButton({ title, onClick, active, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className={`flex h-[32px] items-center gap-6 rounded-8 border border-grey300 px-10 copy-small font-medium shadow-sm transition ${
        active
          ? "bg-primary text-white"
          : "bg-surface text-textPrimary media-hover:hover:bg-grey100"
      }`}
    >
      {children}
    </button>
  );
}

function CenteredState({ children }) {
  return (
    <div className="flex h-full w-full items-center justify-center px-24 text-center">
      {children}
    </div>
  );
}

/**
 * NumericalOverlayViewer — self-contained NetCDF map-overlay player.
 *
 * Pluggable: drop it into any panel. It owns its data (overlay list + manifest),
 * selection (dataset → variable), basemap/opacity, and playback. The map is the focus;
 * configuration lives in a hideable right-side rail and transport in a bottom bar.
 * On mount it scrolls itself into view so the map fills the screen.
 */
export default function NumericalOverlayViewer() {
  const { theme } = useTheme();
  const rootRef = useRef(null);

  const { results, isLoading: listLoading, error: listError } = useMapOverlays();

  const [id, setId] = useState(null);
  useEffect(() => {
    if (!id && results.length) setId(results[0].id);
  }, [results, id]);

  const { manifest, isLoading: manifestLoading } = useMapOverlayManifest(id);

  const [basemap, setBasemap] = useState(() => (theme === "dark" ? "dark" : "light"));
  const [opacity, setOpacity] = useState(0.85);
  const [panelOpen, setPanelOpen] = useState(true);
  const [fitSignal, setFitSignal] = useState(0);

  // ── dataset → variable grouping for the config panel ───────────────────────────
  const datasets = useMemo(() => {
    const seen = new Map();
    for (const r of results) {
      const key = overlayDatasetKey(r);
      if (!seen.has(key)) seen.set(key, { key, label: overlayDatasetLabel(key) });
    }
    return [...seen.values()];
  }, [results]);

  const current = useMemo(() => results.find((r) => r.id === id) ?? null, [results, id]);
  const currentDatasetKey = current ? overlayDatasetKey(current) : null;

  const variables = useMemo(
    () =>
      results
        .filter((r) => overlayDatasetKey(r) === currentDatasetKey)
        .map((r) => ({ id: r.id, label: overlayVariableLabel(r) })),
    [results, currentDatasetKey],
  );

  const onSelectDataset = useCallback(
    (key) => {
      const first = results.find((r) => overlayDatasetKey(r) === key);
      if (first) setId(first.id);
    },
    [results],
  );

  // ── playback ───────────────────────────────────────────────────────────────────
  const frameUrlFor = useCallback(
    (i) => (manifest ? overlayFrameUrl(manifest, manifest.frames[i]?.url) : ""),
    [manifest],
  );
  const player = useOverlayPlayer(manifest, frameUrlFor);

  // ── scroll into view on first mount (tab just opened) ──────────────────────────
  useEffect(() => {
    const t = setTimeout(() => {
      rootRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      ref={rootRef}
      className="relative isolate h-[78vh] min-h-[540px] w-full overflow-hidden rounded-8 border border-grey300 bg-surface"
      style={{ scrollMarginTop: 72 }}
    >
      {/* Map layer */}
      {listError ? (
        <CenteredState>
          <p className="copy-body text-textSecondary">
            Couldn&apos;t load overlays. Please refresh or try again later.
          </p>
        </CenteredState>
      ) : listLoading ? (
        <CenteredState>
          <Spinner isLoading size={32} />
        </CenteredState>
      ) : results.length === 0 ? (
        <CenteredState>
          <p className="copy-body text-textSecondary">
            No numerical overlays are available for this site yet.
          </p>
        </CenteredState>
      ) : (
        <>
          <OverlayRasterMap
            bbox={manifest?.bbox}
            frameUrl={player.currentUrl}
            opacity={opacity}
            mapStyle={OVERLAY_BASEMAPS[basemap]}
            fitSignal={fitSignal}
            panelOpen={panelOpen}
          />

          {/* Top-left toolbar — config toggle + fit */}
          <div className="absolute left-12 top-12 z-[400] flex items-center gap-8">
            <MapToolButton
              title={panelOpen ? "Hide configuration" : "Show configuration"}
              onClick={() => setPanelOpen((v) => !v)}
              active={panelOpen}
            >
              <ControlPanelIcon size={15} />
              <span className="hidden 768:inline">Configure</span>
            </MapToolButton>
            <MapToolButton
              title="Fit overlay to view"
              onClick={() => setFitSignal((n) => n + 1)}
            >
              <FitToFleetIcon size={14} />
            </MapToolButton>
          </div>

          {/* Top-right colour legend — hidden while the config rail is open (it slides in
              from the right and would otherwise sit on top of the legend). */}
          {manifest && !panelOpen && (
            <div className="absolute right-12 top-12 z-[400]">
              <OverlayColorbar
                colorScale={manifest.color_scale}
                variable={manifest.variable}
              />
            </div>
          )}

          {/* Loading pill while the selected variable's manifest resolves */}
          {manifestLoading && (
            <div className="absolute left-1/2 top-12 z-[400] -translate-x-1/2 rounded-8 border border-grey300 bg-surface px-12 py-6 copy-extrasmall text-textSecondary shadow-sm">
              Loading frames…
            </div>
          )}

          {/* Bottom playback bar */}
          {manifest && (
            <div className="pointer-events-none absolute inset-x-0 bottom-12 z-[400] flex justify-center px-12">
              <div className="w-full max-w-[680px]">
                <OverlayPlaybackBar player={player} />
              </div>
            </div>
          )}

          {/* Hideable right-side configuration rail */}
          <OverlayConfigPanel
            open={panelOpen}
            onClose={() => setPanelOpen(false)}
            datasets={datasets}
            selectedDatasetKey={currentDatasetKey}
            onSelectDataset={onSelectDataset}
            variables={variables}
            selectedVariableId={id}
            onSelectVariable={setId}
            basemap={basemap}
            onBasemap={setBasemap}
            opacity={opacity}
            onOpacity={setOpacity}
            manifest={manifest}
            colorScale={manifest?.color_scale}
            variable={manifest?.variable}
            player={manifest ? player : null}
          />
        </>
      )}
    </div>
  );
}
