import { useEffect, useState } from "react";

const SSR_THEME = {
  bg: "#ffffff",
  surface: "#ffffff",
  textPrimary: "#002121",
  textSecondary: "#777979",
  grid: "rgba(0,0,0,0.07)",
  border: "rgba(0,33,33,0.14)",
  isDark: false,
};

function readTheme() {
  if (typeof window === "undefined") return SSR_THEME;
  const s = getComputedStyle(document.documentElement);
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  return {
    bg: s.getPropertyValue("--surface").trim() || SSR_THEME.bg,
    surface: s.getPropertyValue("--surface").trim() || SSR_THEME.surface,
    textPrimary:
      s.getPropertyValue("--text-primary").trim() || SSR_THEME.textPrimary,
    textSecondary:
      s.getPropertyValue("--text-secondary").trim() || SSR_THEME.textSecondary,
    grid: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.07)",
    border: s.getPropertyValue("--grey-300").trim() || SSR_THEME.border,
    isDark,
  };
}

/**
 * Read theme-aware CSS variables for d3 chart styling. Re-evaluates when
 * the document's `data-theme` attribute changes (the existing
 * ThemeProvider toggle flips that attribute).
 *
 * Returns hex/rgba strings that can be used directly as d3 stroke/fill
 * values — no further resolution needed inside the chart code.
 */
export default function useChartTheme() {
  // Start with the SSR default so server + first client render agree;
  // the effect below swaps in the real values after mount.
  const [theme, setTheme] = useState(SSR_THEME);

  useEffect(() => {
    setTheme(readTheme());
    if (typeof MutationObserver === "undefined") return;
    const mo = new MutationObserver((muts) => {
      if (muts.some((m) => m.attributeName === "data-theme")) {
        setTheme(readTheme());
      }
    });
    mo.observe(document.documentElement, { attributes: true });
    return () => mo.disconnect();
  }, []);

  return theme;
}
