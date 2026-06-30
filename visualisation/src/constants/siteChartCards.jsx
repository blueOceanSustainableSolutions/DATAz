/**
 * Chart card catalogue for /site/[id].
 *
 * Single declarative source of truth: ChartGrid reads this table per
 * active tab and emits one ChartCardController per entry. Adding a
 * chart = one row here + one flag in HYDROTWIN_TYPE_REGISTRY's
 * `participatesIn` for every type that should appear in the picker.
 *
 * Card shape:
 *   id            string  — must match a `participatesIn` key in hydrotwinTypeRegistry.js
 *   title         string  — header label
 *   subtitle      string? — small label next to the title
 *   mode          'single' | 'multi' — picker behaviour
 *   component     'line' | 'heatmap' | 'ribbon' — selects the d3 primitive
 *   metric        string  — backend metric path token (see backend handoff §B3.2)
 *   valueKey      string? — for `line` cards, the row field to plot when there is only one
 *   valueKeys     string[]? — for `line` cards plotting two related series from the same row
 *                  (e.g. peak_period + mean_period)
 *   dualAxis      boolean? — `line` cards with left + right y-axis (Temperature & Humidity)
 *   extraControls string? — declarative extra-control id consumed by ChartCardController
 *                  (e.g. 'freqBand' for the octave-band picker)
 *   colorScale    'viridis' | 'diverging'? — for `heatmap` cards
 */

export const SITE_CHART_CARDS = {
  acoustic: [
    {
      id: "aiDetections",
      title: "AI Detections",
      mode: "multi",
      component: "aiDetections",
      metric: "ai_detections",
      icon: "ai",
      typeFilter: true,
    },
    {
      id: "broadbandSPL",
      title: "Broadband Sound Pressure Level",
      mode: "multi",
      component: "line",
      metric: "volume",
      valueKey: "volume",
      icon: "speaker",
      typeFilter: true,
    },
    {
      id: "octaveBands",
      title: "⅓ Octave Bands Sound Pressure Level",
      mode: "multi",
      component: "line",
      metric: "spl",
      icon: "bars",
      typeFilter: true,
    },
    {
      id: "spectrogram",
      title: "Spectrogram",
      mode: "single",
      component: "heatmap",
      metric: "spl",
      colorScale: "viridis",
      icon: "grid",
    },
    {
      id: "anomaly",
      title: "Anomaly summary",
      mode: "single",
      component: "heatmap",
      metric: "spl",
      colorScale: "diverging",
      icon: "anomaly",
    },
  ],
  metocean: [
    {
      id: "waveHeight",
      title: "Significant Wave height",
      mode: "multi",
      component: "line",
      metric: "wave",
      valueKey: "significantWaveHeight",
      icon: "wave",
    },
    {
      id: "wavePeriod",
      title: "Wave Period",
      mode: "multi",
      component: "line",
      metric: "wave",
      valueKeys: ["peakPeriod", "meanPeriod"],
      icon: "clock",
    },
    {
      id: "waveDirection",
      title: "Wave Direction",
      mode: "multi",
      component: "line",
      metric: "wave",
      valueKey: "meanDirection",
      icon: "compass",
    },
    {
      id: "wind",
      title: "Wind Speed and Direction",
      mode: "multi",
      component: "line",
      metric: "wind",
      valueKey: "speed",
      icon: "wind",
    },
    {
      id: "barometric",
      title: "Barometric Pressure",
      mode: "multi",
      component: "line",
      metric: "barometer",
      valueKey: "pressure",
      icon: "gauge",
    },
    {
      id: "dissolvedOxygen",
      title: "Dissolved Oxygen",
      mode: "multi",
      component: "line",
      metric: "dissolved_oxygen",
      valueKey: "dissolvedOxygen",
      icon: "drop",
    },
    {
      id: "current",
      title: "Current",
      mode: "multi",
      component: "line",
      metric: "current",
      valueKey: "speed",
      icon: "flow",
    },
    {
      id: "tempHumidity",
      title: "Temperature & Humidity",
      mode: "multi",
      component: "line",
      metric: "humidity",
      valueKeys: ["temperature", "humidity"],
      dualAxis: true,
      icon: "thermometer",
    },
  ],
  system: [
    {
      id: "energy",
      title: "Energy",
      mode: "multi",
      component: "line",
      metric: "energy",
      valueKeys: ["batteryVoltage", "solarVoltage"],
      icon: "battery",
    },
  ],
};

export const SITE_TAB_IDS = ["acoustic", "metocean", "system"];

export const SITE_TAB_LABELS = {
  acoustic: "Acoustic Analysis",
  metocean: "Metocean Analysis",
  system: "System Status Analysis",
};

/**
 * Tab catalogue consumed by the orchestrator (resolveVisibleTabs). `order`
 * drives default-tab selection and on-screen tab order. Adding a tab = one row
 * here + cards in SITE_CHART_CARDS that reference its id.
 */
export const SITE_TABS = SITE_TAB_IDS.map((id, i) => ({
  id,
  label: SITE_TAB_LABELS[id],
  order: i + 1,
}));

/**
 * Flattened graph catalogue: every card tagged with the tab it belongs to, in
 * tab order then array order (== on-screen render order). This is the single
 * list the orchestrator reasons over.
 */
export const SITE_GRAPHS = SITE_TABS.flatMap((t) =>
  (SITE_CHART_CARDS[t.id] ?? []).map((card) => ({ ...card, tabId: t.id })),
);

/**
 * Distinct measurement metrics backing the charts — the set the availability
 * probe fans out over. Excludes the AI-detections slot (its own endpoint) and
 * the ribbon/coming-soon placeholders.
 */
export const SITE_MEASUREMENT_METRICS = [
  ...new Set(
    SITE_GRAPHS.filter(
      (g) => g.component !== "aiDetections" && g.component !== "ribbon" && g.metric,
    ).map((g) => g.metric),
  ),
];
