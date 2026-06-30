import { useRef, useCallback, useEffect, useMemo, useState } from "react";
import Map, { Source, Layer, Popup, NavigationControl } from "react-map-gl/maplibre";
import { useTheme } from "@/context/ThemeProvider";
import { getHydrotwinTypeKey } from "@/constants/hydrotwinTypeRegistry";
import { STATUS_HEX, STATUS_LABELS } from "@/constants/statusConfig";

// Free, token-less raster basemaps (MapLibre). The marker/trail layers use
// custom canvas icons + circle/line layers, so no sprite or glyph server is
// needed and the open build requires no map provider key.
function rasterStyle(tiles, attribution) {
  return {
    version: 8,
    sources: { basemap: { type: "raster", tiles, tileSize: 256, attribution } },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

const MAP_STYLES = {
  light: rasterStyle(
    ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    "© OpenStreetMap contributors",
  ),
  dark: rasterStyle(
    [
      "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    ],
    "© OpenStreetMap contributors, © CARTO",
  ),
};

function getStatusHex(status) {
  return STATUS_HEX[status?.toLowerCase?.()] ?? "#b5b8b8";
}

const MONTHS =["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function fmtTrailTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${MONTHS[d.getUTCMonth()]} ${pad(d.getUTCDate())} · ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}
function fmtTrailCoords(lat, lon) {
  const latDir = lat >= 0 ? "N" : "S";
  const lonDir = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(4)}°${latDir}, ${Math.abs(lon).toFixed(4)}°${lonDir}`;
}

// Canvas icon matching design buildMarkerSVG (shape + letter)
const ICON_SIZE = 32;
const TYPE_TO_SHAPE = { S: "circle", C: "square", V: "diamond" };

function getShape(typeKey) {
  if (!typeKey) return "circle";
  return TYPE_TO_SHAPE[typeKey.split("-")[1]] ?? "circle";
}

// Solid-fill icon with letter: status color background, white outline, white letter
function drawHtIcon(shape, fillColor, letter) {
  const dpr = 2;
  const px = ICON_SIZE * dpr;
  const canvas = document.createElement("canvas");
  canvas.width = px;
  canvas.height = px;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const cx = ICON_SIZE / 2;
  const cy = ICON_SIZE / 2;

  ctx.fillStyle = fillColor;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2;

  ctx.beginPath();
  if (shape === "square") {
    ctx.roundRect(7, 7, 18, 18, 2);
  } else if (shape === "diamond") {
    ctx.moveTo(cx, 8);
    ctx.lineTo(cx + 8, cy);
    ctx.lineTo(cx, cy + 8);
    ctx.lineTo(cx - 8, cy);
    ctx.closePath();
  } else {
    ctx.arc(cx, cy, 9, 0, Math.PI * 2);
  }
  ctx.fill();
  ctx.stroke();

  // Draw letter centred in the shape
  if (letter) {
    ctx.fillStyle = "#ffffff";
    ctx.font = `500 10px -apple-system, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(letter, cx, cy + 0.5);
  }

  const imageData = ctx.getImageData(0, 0, px, px);
  return { width: px, height: px, data: new Uint8Array(imageData.data.buffer), pixelRatio: dpr };
}

function htIconName(shape, fillColor, letter) {
  return `ht-${shape}-${fillColor.replace("#", "")}-${letter}`;
}

function registerHtIcons(map, hydrotwins) {
  for (const ht of hydrotwins) {
    const typeKey = getHydrotwinTypeKey(ht.htId);
    const shape = getShape(typeKey);
    const fill = getStatusHex(ht.status);
    const letter = typeKey ? typeKey.split("-")[1] : "?";
    const name = htIconName(shape, fill, letter);
    if (map.hasImage(name)) continue;
    const { width, height, data, pixelRatio } = drawHtIcon(shape, fill, letter);
    map.addImage(name, { width, height, data }, { pixelRatio });
  }
}

const pointLayer = {
  id: "ht-points",
  type: "symbol",
  layout: {
    "icon-image": ["get", "icon"],
    "icon-size": 1,
    "icon-allow-overlap": true,
    "icon-anchor": "center",
  },
};

// Trail connecting line. Two layers, one per trail style (data-driven dasharray is avoided):
// HT-S drift → dashed; HT-V track → solid. Both colour by status per-feature.
const driftTrailLayer = {
  id: "ht-trail-drift",
  type: "line",
  filter: ["==", ["get", "htType"], "S"],
  layout: { "line-cap": "round", "line-join": "round" },
  paint: {
    "line-color": ["get", "color"],
    "line-width": 2,
    "line-opacity": 0.45,
    "line-dasharray": [2, 2],
  },
};

const trackTrailLayer = {
  id: "ht-trail-track",
  type: "line",
  filter: ["==", ["get", "htType"], "V"],
  layout: { "line-cap": "round", "line-join": "round" },
  paint: {
    "line-color": ["get", "color"],
    "line-width": 2,
    "line-opacity": 0.5,
  },
};

// Fading position dots (one per GPS ping) — newest brightest, oldest faint — matching the
// AIS-history / deployment-page visualisation. The latest position is the brightest dot.
const trailDotsLayer = {
  id: "ht-trail-dots",
  type: "circle",
  paint: {
    "circle-radius": ["get", "radius"],
    "circle-color": ["get", "color"],
    "circle-opacity": ["get", "opacity"],
    "circle-stroke-width": 0.75,
    "circle-stroke-color": "#ffffff",
    "circle-stroke-opacity": ["get", "opacity"],
  },
};

const INTERACTIVE_LAYERS = ["ht-points"];
// Layers queried on hover (markers + trail position dots).
const HOVER_LAYERS = ["ht-points", "ht-trail-dots"];

function FitAllIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13 }}>
      <path d="M3 7V3h4M17 3h4v4M21 17v4h-4M7 21H3v-4" />
    </svg>
  );
}

/**
 * SiteMap — MapLibre map of the site's devices.
 *
 * - Theme-aware: dark-v11 (night) in dark mode, light-v11 in light mode.
 * - Movement trails (HT-S / HT-V) render as fading position dots + a dashed/solid
 *   connecting line, with per-dot hover — mirroring the deployment page's
 *   AIS-history visualisation. HT-C is stationary.
 * - Clicking a hydrotwin in the rail (selectedHtId change) flies the camera to it.
 * - "Fit all" button restores the full-site view.
 * - Clicking a marker calls onHydrotwinClick.
 *
 * Props:
 *   hydrotwins        Array<HydrotwinDTO>
 *   selectedHtId      string | null
 *   onHydrotwinClick  (htId: string | null) => void   — null when selection is cleared (fitAll)
 *   trailsByHtId      Map<string, Array<{ lng, lat, t }>>  — optional HT-S / HT-V trails
 */
export default function SiteMap({
  hydrotwins = [],
  selectedHtId,
  onHydrotwinClick,
  trailsByHtId,
}) {
  const { theme } = useTheme();
  const mapRef = useRef(null);
  const [popup, setPopup] = useState(null);
  const [legendOpen, setLegendOpen] = useState(false);
  const legendRef = useRef(null);
  const [mapStyle, setMapStyle] = useState(theme === "dark" ? "dark" : "light");

  // Close the movement legend when clicking anywhere outside it.
  useEffect(() => {
    if (!legendOpen) return;
    const onDown = (e) => {
      if (!legendRef.current?.contains(e.target)) setLegendOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [legendOpen]);

  // Sync map style when theme changes
  useEffect(() => {
    setMapStyle(theme === "dark" ? "dark" : "light");
  }, [theme]);

  const [viewState, setViewState] = useState({ longitude: 0, latitude: 20, zoom: 2 });

  // ── helpers ────────────────────────────────────────────────────────────────

  const validPoints = useMemo(() =>
    hydrotwins.filter((ht) => ht.coords?.latitude != null && ht.coords?.longitude != null),
    [hydrotwins],
  );

  const fitAll = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map || validPoints.length === 0) return;
    if (validPoints.length === 1) {
      map.flyTo({ center: [validPoints[0].coords.longitude, validPoints[0].coords.latitude], zoom: 10, duration: 800 });
    } else {
      const lngs = validPoints.map((p) => p.coords.longitude);
      const lats = validPoints.map((p) => p.coords.latitude);
      map.fitBounds(
        [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
        { padding: 64, duration: 800, maxZoom: 14 },
      );
    }
    onHydrotwinClick(null);
  }, [validPoints, onHydrotwinClick]);

  // ── initial fit ────────────────────────────────────────────────────────────
  const [initialFitDone, setInitialFitDone] = useState(false);
  useEffect(() => {
    if (initialFitDone || validPoints.length === 0) return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    fitAll();
    setInitialFitDone(true);
  }, [validPoints, initialFitDone, fitAll]);

  // ── fly to selected HT when selection changes (from rail click) ────────────
  useEffect(() => {
    if (!selectedHtId) return;
    const ht = hydrotwins.find((h) => h.htId === selectedHtId);
    if (!ht?.coords?.latitude) return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    map.flyTo({
      center: [ht.coords.longitude, ht.coords.latitude],
      zoom: Math.max(map.getZoom(), 9),
      duration: 600,
    });
  }, [selectedHtId, hydrotwins]);

  // ── markers GeoJSON ──────────────────────────────────────────────────────────
  const geojson = useMemo(() => ({
    type: "FeatureCollection",
    features: validPoints.map((ht) => {
      const typeKey = getHydrotwinTypeKey(ht.htId);
      const shape = getShape(typeKey);
      const fill = getStatusHex(ht.status);
      const letter = typeKey ? typeKey.split("-")[1] : "?";
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [ht.coords.longitude, ht.coords.latitude] },
        properties: {
          htId: ht.htId,
          icon: htIconName(shape, fill, letter),
          statusLabel: STATUS_LABELS[ht.status?.toLowerCase?.()] ?? "",
          location: ht.location ?? "",
        },
      };
    }),
  }), [validPoints]);

  // ── trail GeoJSON: connecting lines + fading dots ──────────
  const { trailLineGeojson, trailDotsGeojson } = useMemo(() => {
    const lines = [];
    const dots = [];
    if (trailsByHtId?.size) {
      for (const ht of hydrotwins) {
        const typeKey = getHydrotwinTypeKey(ht.htId);
        // HT-S drifts and HT-V tracks; HT-C is stationary (no trail).
        if (typeKey !== "HT-S" && typeKey !== "HT-V") continue;
        const pts = trailsByHtId.get(ht.htId);
        if (!pts?.length) continue;

        const color = getStatusHex(ht.status);
        const htType = typeKey.split("-")[1];
        const coords = pts.map((p) => [p.lng, p.lat]);

        lines.push({
          type: "Feature",
          geometry: { type: "LineString", coordinates: coords },
          properties: { color, htType },
        });

        const n = pts.length;
        pts.forEach((p, i) => {
          const isLatest = i === n - 1;
          // Newest brightest → oldest faint (recency cue); latest is the brightest dot.
          const opacity = n === 1 ? 1 : Math.max(0.2, 0.2 + (i / (n - 1)) * 0.8);
          dots.push({
            type: "Feature",
            geometry: { type: "Point", coordinates: [p.lng, p.lat] },
            properties: {
              color,
              opacity,
              radius: isLatest ? 4 : 3,
              htId: ht.htId,
              timeLabel: fmtTrailTime(p.t),
              coordsLabel: fmtTrailCoords(p.lat, p.lng),
            },
          });
        });

      }
    }
    return {
      trailLineGeojson: lines.length ? { type: "FeatureCollection", features: lines } : null,
      trailDotsGeojson: dots.length ? { type: "FeatureCollection", features: dots } : null,
    };
  }, [hydrotwins, trailsByHtId]);

  // ── icon registration ───────────────────────────────────────────────────────
  // Store the map instance as state so effects that depend on it re-run once
  // the map is actually ready (mapRef.current is null at mount time).
  const [mapInstance, setMapInstance] = useState(null);

  const handleStyleLoad = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    setMapInstance(map);          // triggers the effects below on first load
    registerHtIcons(map, hydrotwins);
  }, [hydrotwins]);

  // Attach styleimagemissing once the map is available.
  // This fires whenever a layer references an icon name that isn't registered —
  // the name encodes shape+color+letter so we can draw it on-demand.
  // MapLibre automatically repaints after an image is added inside this handler.
  useEffect(() => {
    if (!mapInstance) return;

    function onImageMissing(e) {
      const parts = e.id.split("-"); // ht-<shape>-<hex6>-<letter>
      if (parts[0] !== "ht" || parts.length < 4) return;
      if (mapInstance.hasImage(e.id)) return;
      const { width, height, data, pixelRatio } = drawHtIcon(parts[1], "#" + parts[2], parts[3]);
      mapInstance.addImage(e.id, { width, height, data }, { pixelRatio });
    }

    mapInstance.on("styleimagemissing", onImageMissing);
    return () => mapInstance.off("styleimagemissing", onImageMissing);
  }, [mapInstance]);

  // When hydrotwins arrive (after the map is ready), pre-register all icons and
  // force a repaint so MapLibre re-evaluates the symbol layer immediately.
  useEffect(() => {
    if (!mapInstance) return;
    registerHtIcons(mapInstance, hydrotwins);
    mapInstance.triggerRepaint();
  }, [mapInstance, hydrotwins]);

  // ── dynamic icon size for selected ─────────────────────────────────────────
  const dynamicPointLayout = useMemo(() => ({
    ...pointLayer.layout,
    "icon-size": selectedHtId
      ? ["case", ["==", ["get", "htId"], selectedHtId], 1.35, 1]
      : 1,
  }), [selectedHtId]);

  // ── interaction handlers ────────────────────────────────────────────────────
  const handleClick = useCallback((event) => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const features = map.queryRenderedFeatures(event.point, { layers: INTERACTIVE_LAYERS });
    if (features.length > 0) {
      const htId = features[0].properties.htId;
      if (htId && onHydrotwinClick) onHydrotwinClick(htId);
    }
  }, [onHydrotwinClick]);

  const handleMouseMove = useCallback((event) => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const layers = HOVER_LAYERS.filter((id) => {
      try { return !!map.getLayer(id); } catch { return false; }
    });
    const features = layers.length
      ? map.queryRenderedFeatures(event.point, { layers })
      : [];
    if (features.length > 0) {
      map.getCanvas().style.cursor = "pointer";
      const f = features[0];
      const props = f.properties;
      const coords = f.geometry.coordinates;
      if (f.layer.id === "ht-trail-dots") {
        setPopup({ lon: coords[0], lat: coords[1], type: "dot", htId: props.htId, timeLabel: props.timeLabel, coordsLabel: props.coordsLabel });
      } else {
        setPopup({ lon: coords[0], lat: coords[1], type: "marker", htId: props.htId, status: props.statusLabel, location: props.location });
      }
    } else {
      map.getCanvas().style.cursor = "";
      setPopup(null);
    }
  }, []);

  const handleMouseLeave = useCallback(() => setPopup(null), []);

  // ── button style ────────────────────────────────────────────────────────────
  const ctrlBtn = {
    position: "absolute",
    top: 12,
    right: 12,
    zIndex: 400,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 10px",
    borderRadius: 8,
    fontSize: 12,
    fontWeight: 500,
    color: "var(--text-primary)",
    background: "var(--surface)",
    border: "0.5px solid var(--grey-300)",
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 2px 6px rgba(0,0,0,0.08)",
    userSelect: "none",
    transition: "background 0.15s",
  };

  // Movement legend — line styles (positions are self-evident dots).
  const legendBox = {
    position: "absolute",
    bottom: 12,
    left: 12,
    zIndex: 400,
    background: "var(--surface)",
    border: "0.5px solid var(--grey-300)",
    borderRadius: 8,
    padding: "8px 10px",
    boxShadow: "0 2px 6px rgba(0,0,0,0.08)",
    fontFamily: "inherit",
    userSelect: "none",
  };
  const legendTitle = {
    fontSize: 10,
    fontWeight: 500,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-secondary)",
    marginBottom: 6,
  };
  const legendRow = {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 12,
    color: "var(--text-primary)",
    padding: "2px 0",
  };

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <Map
        ref={mapRef}
        {...viewState}
        onMove={(e) => setViewState(e.viewState)}
        mapStyle={MAP_STYLES[mapStyle]}
        style={{ width: "100%", height: "100%" }}
        interactiveLayerIds={INTERACTIVE_LAYERS}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onLoad={handleStyleLoad}
        onStyleData={handleStyleLoad}
      >
        <NavigationControl position="bottom-right" />

        {/* Trail connecting line (dashed HT-S / solid HT-V), beneath the dots */}
        {trailLineGeojson && (
          <Source id="ht-trail-lines" type="geojson" data={trailLineGeojson}>
            <Layer {...driftTrailLayer} />
            <Layer {...trackTrailLayer} />
          </Source>
        )}

        {/* Fading position dots */}
        {trailDotsGeojson && (
          <Source id="ht-trail-dots-src" type="geojson" data={trailDotsGeojson}>
            <Layer {...trailDotsLayer} />
          </Source>
        )}

        <Source id="ht-markers" type="geojson" data={geojson}>
          <Layer {...pointLayer} layout={dynamicPointLayout} />
        </Source>

        {popup && (
          <Popup
            longitude={popup.lon}
            latitude={popup.lat}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={14}
            className="dashboard-map-popup"
          >
            {popup.type === "dot" ? (
              <div className="copy-small">
                <p className="font-bold">{popup.htId}</p>
                {popup.timeLabel && <p className="text-grey500">{popup.timeLabel}</p>}
                {popup.coordsLabel && <p className="text-grey500">{popup.coordsLabel}</p>}
              </div>
            ) : (
              <div className="copy-small">
                <p className="font-bold">{popup.htId}</p>
                <p className="text-grey500">{popup.status}</p>
                {popup.location && <p className="text-grey500">{popup.location}</p>}
              </div>
            )}
          </Popup>
        )}
      </Map>

      {/* Fit all button — top right, above NavigationControl */}
      <button style={ctrlBtn} onClick={fitAll} title="Fit all hydrotwins">
        <FitAllIcon />
        Fit all
      </button>

      {/* Movement legend — collapsible chip (collapsed by default so it never
          covers a hydrotwin marker or the header). */}
      <div
        ref={legendRef}
        onMouseEnter={() => setLegendOpen(true)}
        onMouseLeave={() => setLegendOpen(false)}
        style={{ position: "absolute", bottom: 12, left: 12, zIndex: 400, userSelect: "none" }}
      >
        {legendOpen ? (
          <div style={{ ...legendBox, position: "static", bottom: "auto", left: "auto", zIndex: "auto" }}>
            <button
              type="button"
              onClick={() => setLegendOpen(false)}
              style={{ ...legendTitle, display: "flex", alignItems: "center", gap: 6, marginBottom: 6, background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit" }}
            >
              Movement
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden style={{ transform: "rotate(180deg)" }}>
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
            <div style={legendRow}>
              <svg width="22" height="8" style={{ flexShrink: 0 }} aria-hidden>
                <line x1="1" y1="4" x2="21" y2="4" stroke="var(--text-secondary)" strokeWidth="2" strokeDasharray="2 3" strokeLinecap="round" />
              </svg>
              HT-S · Drifting
            </div>
            <div style={legendRow}>
              <svg width="22" height="8" style={{ flexShrink: 0 }} aria-hidden>
                <line x1="1" y1="4" x2="21" y2="4" stroke="var(--text-secondary)" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
              HT-V · Vessel
            </div>
            <div style={legendRow}>
              <span style={{ width: 22, textAlign: "center", flexShrink: 0, color: "var(--text-secondary)" }}>•</span>
              HT-C · Stationary
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setLegendOpen(true)}
            title="Show movement legend"
            style={{
              ...legendBox,
              position: "static", bottom: "auto", left: "auto", zIndex: "auto",
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "5px 9px", cursor: "pointer",
              color: "var(--text-primary)", fontSize: 12, fontWeight: 500,
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ flexShrink: 0, color: "var(--text-secondary)" }}
              aria-hidden
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
            Movement
          </button>
        )}
      </div>
    </div>
  );
}
