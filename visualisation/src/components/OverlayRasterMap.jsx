import { useRef, useCallback, useEffect, useState, useMemo } from "react";
import Map, { NavigationControl } from "react-map-gl/maplibre";

const SRC = "overlay-frame";
const LAYER = "overlay-frame-layer";

// Image-source corners in order: TL, TR, BR, BL (each [lng, lat]).
// Frames are rendered north-up, so the image's top edge maps to bbox.north.
function corners(b) {
  return [
    [b.west, b.north],
    [b.east, b.north],
    [b.east, b.south],
    [b.west, b.south],
  ];
}

/**
 * OverlayRasterMap — a MapLibre basemap with a single time-animated raster overlay.
 *
 * Token-less: the basemap is a plain raster style object (OVERLAY_BASEMAPS), so the
 * open build needs no map-provider key. The overlay is an `image` source whose PNG is
 * swapped imperatively per frame (`updateImage`) so playback never re-creates the
 * layer. The basemap style can change underneath it (light/dark/satellite); MapLibre
 * wipes custom layers on a style reload, so we re-add the overlay on `style.load`. The
 * camera fits the overlay bbox on first load, whenever the dataset's bbox changes, and
 * whenever `fitSignal` is bumped.
 */
const PANEL_WIDTH = 300; // matches OverlayConfigPanel w-[300px]

export default function OverlayRasterMap({
  bbox,
  frameUrl,
  opacity = 0.85,
  mapStyle,
  fitSignal = 0,
  panelOpen = false,
}) {
  const mapRef = useRef(null);
  const [mapInstance, setMapInstance] = useState(null);
  const opacityRef = useRef(opacity);
  const fittedKeyRef = useRef(null);

  const coordinates = useMemo(() => (bbox ? corners(bbox) : null), [bbox]);
  const bboxKey = bbox ? `${bbox.west},${bbox.south},${bbox.east},${bbox.north}` : "";

  const initialViewState = useMemo(() => {
    if (!bbox) return { longitude: -30.9, latitude: 37.5, zoom: 4 };
    return {
      longitude: (bbox.west + bbox.east) / 2,
      latitude: (bbox.south + bbox.north) / 2,
      zoom: 4,
    };
  }, [bbox]);

  // Add the overlay source/layer if missing, then swap the image + apply opacity.
  const addOrUpdateOverlay = useCallback(
    (map) => {
      if (!map || !coordinates || !frameUrl) return;
      const src = map.getSource(SRC);
      if (!src) {
        map.addSource(SRC, { type: "image", url: frameUrl, coordinates });
        map.addLayer({
          id: LAYER,
          type: "raster",
          source: SRC,
          paint: {
            "raster-opacity": opacityRef.current,
            "raster-fade-duration": 0,
          },
        });
      } else {
        src.updateImage({ url: frameUrl, coordinates });
        if (map.getLayer(LAYER)) {
          map.setPaintProperty(LAYER, "raster-opacity", opacityRef.current);
        }
      }
    },
    [coordinates, frameUrl],
  );

  const fitToBbox = useCallback(
    (map, animate) => {
      if (!map || !bbox) return;
      map.fitBounds(
        [
          [bbox.west, bbox.south],
          [bbox.east, bbox.north],
        ],
        {
          padding: { top: 48, bottom: 48, left: 48, right: panelOpen ? 48 + PANEL_WIDTH : 48 },
          duration: animate ? 700 : 0,
        },
      );
    },
    [bbox, panelOpen],
  );

  const handleLoad = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    setMapInstance(map);
  }, []);

  // Swap the frame / opacity whenever they change (once the map is ready).
  useEffect(() => {
    if (!mapInstance) return;
    addOrUpdateOverlay(mapInstance);
  }, [mapInstance, addOrUpdateOverlay]);

  // Live opacity without re-adding the layer.
  useEffect(() => {
    opacityRef.current = opacity;
    if (mapInstance && mapInstance.getLayer(LAYER)) {
      mapInstance.setPaintProperty(LAYER, "raster-opacity", opacity);
    }
  }, [mapInstance, opacity]);

  // A basemap switch reloads the style and drops custom layers — re-add the overlay.
  useEffect(() => {
    if (!mapInstance) return;
    const reAdd = () => addOrUpdateOverlay(mapInstance);
    mapInstance.on("style.load", reAdd);
    return () => mapInstance.off("style.load", reAdd);
  }, [mapInstance, addOrUpdateOverlay]);

  // Fit the camera to the overlay on first ready and on bbox change (new dataset).
  useEffect(() => {
    if (!mapInstance || !bbox) return;
    const animate = fittedKeyRef.current !== null && fittedKeyRef.current !== bboxKey;
    fitToBbox(mapInstance, animate);
    fittedKeyRef.current = bboxKey;
  }, [mapInstance, bboxKey, bbox, fitToBbox]);

  // Manual "fit" requests from the toolbar.
  useEffect(() => {
    if (!mapInstance || !fitSignal) return;
    fitToBbox(mapInstance, true);
  }, [mapInstance, fitSignal, fitToBbox]);

  return (
    <Map
      ref={mapRef}
      initialViewState={initialViewState}
      mapStyle={mapStyle}
      style={{ width: "100%", height: "100%" }}
      onLoad={handleLoad}
      attributionControl={false}
    >
      <NavigationControl position="bottom-right" showCompass={false} />
    </Map>
  );
}
