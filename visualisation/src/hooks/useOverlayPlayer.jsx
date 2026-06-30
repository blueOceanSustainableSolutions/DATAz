import { useCallback, useEffect, useRef, useState } from "react";

// Streams frames in rather than bulk-downloading: keeps a small prefetch window warm
// in the browser cache (via Image()), plays as soon as the next frame is ready, and
// raises a buffering flag if playback outruns the prefetch.
const LOOKAHEAD = 16; // frames to prefetch ahead of the playhead
const CACHE_CAP = 140; // max Image() objects kept warm (evict oldest)

/**
 * Frame playback + gradual look-ahead prefetch for a map-overlay manifest.
 *
 * @param manifest      the overlay manifest ({ frames, time }), or null
 * @param frameUrlFor   (index) => absolute frame URL (with SAS token)
 * @returns playback state + controls consumed by OverlayPlaybackBar / OverlayRasterMap
 */
export function useOverlayPlayer(manifest, frameUrlFor) {
  const count = manifest?.frames?.length ?? 0;

  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(30);
  const [step, setStep] = useState(1); // decimation: play every Nth frame
  const [buffering, setBuffering] = useState(false);

  const cacheRef = useRef(new Map()); // index -> { img, status }
  const indexRef = useRef(0);
  useEffect(() => {
    indexRef.current = index;
  }, [index]);

  const isLoaded = useCallback(
    (i) => cacheRef.current.get(i)?.status === "loaded",
    [],
  );

  const prefetch = useCallback(
    (i) => {
      if (i < 0 || i >= count) return;
      const cache = cacheRef.current;
      if (cache.has(i)) return;
      const url = frameUrlFor(i);
      if (!url) return;
      const img = new Image();
      const entry = { img, status: "loading" };
      cache.set(i, entry);
      img.onload = () => {
        entry.status = "loaded";
      };
      img.onerror = () => {
        entry.status = "error";
      };
      img.src = url;
      if (cache.size > CACHE_CAP) {
        const oldest = cache.keys().next().value;
        if (oldest !== i) cache.delete(oldest);
      }
    },
    [count, frameUrlFor],
  );

  const prefetchAhead = useCallback(
    (from) => {
      if (!count) return;
      for (let k = 0; k <= LOOKAHEAD; k++) prefetch((from + k * step) % count);
    },
    [prefetch, step, count],
  );

  // Reset when the manifest changes (a different dataset/variable may have a different
  // frame interval, so reset the decimation step too).
  useEffect(() => {
    cacheRef.current = new Map();
    setIndex(0);
    indexRef.current = 0;
    setBuffering(false);
    const iv = manifest?.time?.interval_seconds;
    setStep(iv && iv > 0 ? Math.max(1, Math.round(3600 / iv)) : 1);
    if (count) {
      prefetch(0);
      prefetchAhead(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest]);

  const seek = useCallback(
    (i) => {
      if (!count) return;
      const ni = ((i % count) + count) % count;
      indexRef.current = ni;
      setIndex(ni);
      prefetch(ni);
      prefetchAhead(ni);
    },
    [count, prefetch, prefetchAhead],
  );

  // RAF playback loop; retries quickly while buffering, advances on a ready frame.
  useEffect(() => {
    if (!playing || !count) return;
    let raf,
      last = performance.now(),
      acc = 0;
    const tick = (ts) => {
      acc += ts - last;
      last = ts;
      const interval = 1000 / Math.max(1, fps);
      if (acc >= interval) {
        const next = (indexRef.current + step) % count;
        if (isLoaded(next)) {
          acc = 0;
          indexRef.current = next;
          setIndex(next);
          setBuffering(false);
          prefetchAhead(next);
        } else {
          setBuffering(true);
          prefetch(next);
          prefetchAhead(indexRef.current);
          // don't reset acc -> retry on the next frame until `next` is ready
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, fps, step, count, isLoaded, prefetch, prefetchAhead]);

  return {
    index,
    count,
    playing,
    setPlaying,
    fps,
    setFps,
    step,
    setStep,
    buffering,
    seek,
    currentUrl: count ? frameUrlFor(index) : null,
    timestamp: manifest?.frames?.[index]?.timestamp ?? null,
    intervalSeconds: manifest?.time?.interval_seconds ?? null,
  };
}
