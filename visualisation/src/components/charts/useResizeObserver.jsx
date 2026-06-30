import { useEffect, useState } from "react";

/**
 * Track a DOM element's content rect with ResizeObserver. Returns
 * { width, height } in CSS pixels, both defaulting to 0 before the first
 * measurement (and during SSR).
 *
 * Used by the d3 chart primitives to redraw on container resize without
 * pulling in a heavier hook from a UI library.
 *
 * @param {React.RefObject<Element|null>} ref
 * @returns {{ width: number, height: number }}
 */
export default function useResizeObserver(ref) {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      // Round to avoid sub-pixel re-renders that don't change anything.
      setSize((prev) => {
        const w = Math.round(width);
        const h = Math.round(height);
        return prev.width === w && prev.height === h ? prev : { width: w, height: h };
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return size;
}
