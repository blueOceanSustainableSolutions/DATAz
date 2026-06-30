/**
 * Site detections folds — collapse per-htId series envelopes from the Site
 * AI-detections API into the single-shaped objects the existing presentational
 * components already consume.
 *
 * The Site endpoints return:
 *   { metric, siteId, startDate, endDate, series: [{ htId, data }, …] }
 * Where each `data` payload mirrors the matching single-hydrotwin response.
 * These folds let us reuse OverviewStatsCard, BinnedAggregatesCard, and
 * RecentDetectionsCard unchanged on the Site page.
 */

// ── Overview ───────────────────────────────────────────────────────────────

const EMPTY_OVERVIEW = {
  uniqueClasses: 0,
  devices: { active: 0, total: 0 },
  intervalMinutes: 1,
  totalEvents: 0,
  leadingCategory: null,
  leadingCategoryPeak: null,
  byCategory: [],
  byHydrotwin: [],
  window: null,
};

export function foldOverviewSeries(series) {
  if (!Array.isArray(series) || series.length === 0) return EMPTY_OVERVIEW;

  let totalEvents = 0;
  let intervalMinutes = 1;
  let uniqueClassesMax = 0;
  let leadingPeak = null;
  let windowStart = null;
  let windowEnd = null;
  const eventsByCategory = new Map();
  const byHydrotwin = [];

  for (const entry of series) {
    const d = entry?.data;
    if (!d) continue;
    totalEvents += Number(d.totalEvents || 0);
    intervalMinutes = Math.max(intervalMinutes, Number(d.intervalMinutes || 1));
    uniqueClassesMax = Math.max(uniqueClassesMax, Number(d.uniqueClasses || 0));

    // Each per-htId payload mirrors the single-hydrotwin overview, which carries
    // `window: { startDate, endDate }`. Fold to the widest span across the series
    // so OverviewStatsCard can render the "Window" duration on the Site page.
    if (d.window) {
      const s = d.window.startDate;
      const e = d.window.endDate;
      if (s && (!windowStart || new Date(s) < new Date(windowStart))) windowStart = s;
      if (e && (!windowEnd || new Date(e) > new Date(windowEnd))) windowEnd = e;
    }

    for (const c of d.byCategory || []) {
      const key = String(c.category || "").toLowerCase();
      eventsByCategory.set(
        key,
        (eventsByCategory.get(key) || 0) + Number(c.events || 0),
      );
    }

    if (d.leadingCategoryPeak) {
      const p = d.leadingCategoryPeak;
      const intensity = Number(p.intensityPercentage || 0);
      if (!leadingPeak || intensity > leadingPeak.intensityPercentage) {
        leadingPeak = {
          intensityPercentage: intensity,
          ingestedAt: p.ingestedAt,
          // Tag the peak with the htId that owned it so the overview card
          // can show "Peak X% @ T · HT-..." in multi-deployment mode.
          htId: entry.htId,
        };
      }
    }

    byHydrotwin.push({
      htId: entry.htId,
      totalEvents: Number(d.totalEvents || 0),
      leadingCategory: d.leadingCategory ?? null,
    });
  }

  const byCategory = [...eventsByCategory.entries()]
    .map(([category, events]) => ({
      category,
      events,
      percentageOfTotal: totalEvents > 0 ? (events / totalEvents) * 100 : 0,
    }))
    .sort((a, b) => b.events - a.events);

  const leadingCategory = byCategory.length > 0 ? byCategory[0].category : null;

  // Best-effort device count — one "active" device per htId in the series.
  const activeDevices = byHydrotwin.filter((b) => b.totalEvents > 0).length;

  return {
    uniqueClasses: uniqueClassesMax,
    devices: { active: activeDevices, total: series.length },
    intervalMinutes,
    totalEvents,
    leadingCategory,
    leadingCategoryPeak: leadingPeak,
    byCategory,
    byHydrotwin,
    window:
      windowStart && windowEnd
        ? { startDate: windowStart, endDate: windowEnd }
        : null,
  };
}

// ── Bins ───────────────────────────────────────────────────────────────────

const EMPTY_BINS = {
  binMinutes: 0,
  intervalMinutes: 1,
  startDate: null,
  endDate: null,
  totalBins: 0,
  bins: [],
};

export function foldBinsSeries(series) {
  if (!Array.isArray(series) || series.length === 0) return EMPTY_BINS;

  // Pick the first non-empty payload as the bin-grid template; backend
  // guarantees every series uses the same effective bin grid so picking
  // any one is safe. Sum categories from every series onto that grid.
  let template = null;
  let binMinutes = 0;
  let intervalMinutes = 1;
  for (const entry of series) {
    const d = entry?.data;
    if (!d?.bins) continue;
    if (!template || d.bins.length > template.length) {
      template = d.bins;
    }
    binMinutes = Math.max(binMinutes, Number(d.binMinutes || 0));
    intervalMinutes = Math.max(intervalMinutes, Number(d.intervalMinutes || 1));
  }

  if (!template) return EMPTY_BINS;

  const startDate = series.find((s) => s?.data?.startDate)?.data?.startDate ?? null;
  const endDate = series.find((s) => s?.data?.endDate)?.data?.endDate ?? null;

  // Sum events per (binStart, category); keep max for peakIntensityPercentage and peakSplDb.
  const byBin = new Map();
  for (const bin of template) {
    const key = typeof bin.binStart === "string"
      ? bin.binStart
      : new Date(bin.binStart).toISOString();
    byBin.set(key, {
      binStart: bin.binStart,
      binEnd: bin.binEnd,
      categories: new Map(),
    });
  }

  for (const entry of series) {
    const bins = entry?.data?.bins;
    if (!Array.isArray(bins)) continue;
    for (const bin of bins) {
      const key = typeof bin.binStart === "string"
        ? bin.binStart
        : new Date(bin.binStart).toISOString();
      const target = byBin.get(key);
      if (!target) continue;
      for (const c of bin.categories || []) {
        const cat = String(c.category || "").toLowerCase();
        const cur = target.categories.get(cat) || {
          category: cat,
          events: 0,
          peakIntensityPercentage: 0,
          peakSplDb: null,
        };
        cur.events += Number(c.events || 0);
        cur.peakIntensityPercentage = Math.max(
          cur.peakIntensityPercentage,
          Number(c.peakIntensityPercentage || 0),
        );
        if (c.peakSplDb != null) {
          cur.peakSplDb = cur.peakSplDb == null
            ? Number(c.peakSplDb)
            : Math.max(cur.peakSplDb, Number(c.peakSplDb));
        }
        target.categories.set(cat, cur);
      }
    }
  }

  const bins = [...byBin.values()].map((b) => ({
    binStart: b.binStart,
    binEnd: b.binEnd,
    categories: [...b.categories.values()],
  }));

  return {
    binMinutes,
    intervalMinutes,
    startDate,
    endDate,
    totalBins: bins.length,
    bins,
  };
}

// ── Recent detections ──────────────────────────────────────────────────────

export function mergeRecentSeries(series, limit = 20) {
  if (!Array.isArray(series) || series.length === 0) {
    return { detections: [], lastUpdated: new Date() };
  }

  const all = [];
  let latestUpdated = null;

  for (const entry of series) {
    const d = entry?.data;
    if (!d) continue;
    const htId = entry.htId;
    for (const det of d.detections || []) {
      all.push({ ...det, htId });
    }
    if (d.lastUpdated) {
      const t = new Date(d.lastUpdated);
      if (!latestUpdated || t > latestUpdated) latestUpdated = t;
    }
  }

  all.sort((a, b) => new Date(b.ingestedAt) - new Date(a.ingestedAt));
  const detections = limit > 0 ? all.slice(0, limit) : all;

  return {
    detections,
    lastUpdated: latestUpdated ?? new Date(),
  };
}

// ── Bin inspection (no fold — just flatten + summarise) ────────────────────

export function flattenBinInspectionSeries(series) {
  if (!Array.isArray(series) || series.length === 0) {
    return {
      events: [],
      acousticAvailable: false,
      summary: { events: 0, peakIntensityPercentage: 0, peakSplDb: null },
    };
  }

  const events = [];
  let acousticAvailable = false;
  let peakIntensityPercentage = 0;
  let peakSplDb = null;

  for (const entry of series) {
    const d = entry?.data;
    if (!d) continue;
    // Only let acoustic-capable hydrotwins that actually have events in this
    // bin flip the flag. The Site endpoint fans out across every htId in the
    // site, so an HT-C unit with zero events here would otherwise force the
    // Acoustic Viewer on for a bin whose only real data is HT-S. Gating on
    // event count keeps the viewer hidden for HT-S-only bins.
    if (d.acousticAvailable && (d.events?.length ?? 0) > 0) {
      acousticAvailable = true;
    }
    if (d.summary) {
      peakIntensityPercentage = Math.max(
        peakIntensityPercentage,
        Number(d.summary.peakIntensityPercentage || 0),
      );
      if (d.summary.peakSplDb != null) {
        peakSplDb = peakSplDb == null
          ? Number(d.summary.peakSplDb)
          : Math.max(peakSplDb, Number(d.summary.peakSplDb));
      }
    }
    for (const e of d.events || []) {
      // Each backend event already carries `htId` + `deploymentId` — pass through.
      events.push(e);
    }
  }

  // Sort by ingestedAt descending so the events list shows most-intense / latest first.
  events.sort((a, b) => new Date(b.ingestedAt) - new Date(a.ingestedAt));

  return {
    events,
    acousticAvailable,
    summary: {
      events: events.length,
      peakIntensityPercentage,
      peakSplDb,
    },
  };
}
