"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { Dialog, Transition } from "@headlessui/react";
import { useQuery } from "@tanstack/react-query";
import { fetchDetectionsBinInspection } from "@/api/detections-overview";
import { useSiteDetectionsBinInspection } from "@/hooks/useSiteDetectionsBinInspection";
import BinInspectionStripChart from "@/components/BinInspectionStripChart";
import BinInspectionBeeswarmChart from "@/components/BinInspectionBeeswarmChart";
import BinInspectionDeploymentLegend from "@/components/BinInspectionDeploymentLegend";
import { getCategoryLabel, formatBinWidthLabel } from "@/lib/detections";
import { flattenBinInspectionSeries } from "@/lib/siteDetections";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";

// ─── Absorbed sub-component: BinInspectionEventsList ────────────────────────

const evPad2 = (n) => String(n).padStart(2, "0");

function formatUtcTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${evPad2(d.getUTCHours())}:${evPad2(d.getUTCMinutes())}:${evPad2(d.getUTCSeconds())} UTC`;
}

function EvTh({ children }) {
  return (
    <th className="border-b border-grey200 bg-grey100 px-14 py-9 text-left font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-textSecondary dark:border-grey300 dark:bg-grey100">
      {children}
    </th>
  );
}

/**
 * Scrollable events table inside BinInspectionModal.
 *
 * When `scopedHydrotwins` is provided the table renders an extra Hydrotwin
 * column with a per-deployment colour swatch — used in multi-deployment mode.
 */
function BinInspectionEventsList({
  events,
  selectedEvent,
  onSelectEvent,
  scopedHydrotwins,
}) {
  if (!events?.length) {
    return (
      <div className="flex items-center justify-center rounded-[8px] border border-dashed border-grey300 bg-grey100 py-24 text-center font-mono text-[12px] text-textSecondary dark:border-grey200">
        No events in this bin.
      </div>
    );
  }

  const showHydrotwin = Boolean(scopedHydrotwins);

  const sorted = [...events].sort(
    (a, b) => new Date(b.ingestedAt).getTime() - new Date(a.ingestedAt).getTime(),
  );

  return (
    <div className="max-h-[280px] overflow-x-auto overflow-y-auto rounded-[8px] border border-grey200 bg-surface scrollbar-thin dark:border-grey300">
      <table className={clsx("w-full border-collapse text-[11px]", showHydrotwin ? "min-w-[420px]" : "min-w-[320px]")}>
        <thead className="sticky top-0 z-[1] bg-grey100 dark:bg-grey100">
          <tr>
            <EvTh>Time</EvTh>
            {showHydrotwin && <EvTh>Hydrotwin</EvTh>}
            <EvTh>Intensity</EvTh>
            <EvTh>SPL (dB)</EvTh>
          </tr>
        </thead>
        <tbody>
          {sorted.map((ev, idx) => {
            const isSelected =
              selectedEvent?.ingestedAt === ev.ingestedAt &&
              selectedEvent?.htId === ev.htId;
            const hasAcoustic = Boolean(ev.audioUrl);
            const pct         = Math.round(Number(ev.intensityPercentage) || 0);
            const splStr      = ev.splDb != null ? Number(ev.splDb).toFixed(1) : "—";
            const htColor = ev.htId && showHydrotwin
              ? getOverlayColor({ htId: ev.htId, scopedHydrotwins })
              : null;

            return (
              <tr
                key={`${ev.htId ?? "scout"}-${ev.ingestedAt}-${idx}`}
                onClick={() => hasAcoustic && onSelectEvent?.(ev)}
                className={clsx(
                  "border-l-[2px] transition-[background,border-color] duration-100",
                  hasAcoustic
                    ? "cursor-pointer"
                    : "cursor-default opacity-60",
                  isSelected
                    ? "border-l-primary bg-primarySelected"
                    : "border-l-transparent hover:bg-grey100",
                  !hasAcoustic && "hover:bg-transparent",
                )}
              >
                <td className="border-b border-grey100 px-14 py-9 font-mono tabular-nums text-textPrimary dark:border-grey200">
                  {formatUtcTime(ev.ingestedAt)}
                </td>
                {showHydrotwin && (
                  <td className="border-b border-grey100 px-14 py-9 font-mono text-textPrimary dark:border-grey200">
                    {ev.htId ? (
                      <div className="flex items-center gap-6">
                        {htColor && (
                          <span
                            className="h-7 w-7 flex-shrink-0 rounded-full"
                            style={{ background: htColor }}
                            aria-hidden
                          />
                        )}
                        <span>{ev.htId}</span>
                      </div>
                    ) : (
                      <span className="text-textSecondary">—</span>
                    )}
                  </td>
                )}
                <td className="border-b border-grey100 px-14 py-9 tabular-nums text-textPrimary dark:border-grey200">
                  {pct}%
                </td>
                <td className="border-b border-grey100 px-14 py-9 tabular-nums text-textPrimary dark:border-grey200">
                  {splStr}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const pad2 = (n) => String(n).padStart(2, "0");

function fmtUtcRange(startIso, endIso) {
  const a = new Date(startIso);
  const b = new Date(endIso);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return "—";
  const dateStr = `${a.toUTCString().slice(8, 11)} ${pad2(a.getUTCDate())}`;
  const tA = `${pad2(a.getUTCHours())}:${pad2(a.getUTCMinutes())}`;
  const tB = `${pad2(b.getUTCHours())}:${pad2(b.getUTCMinutes())}`;
  return `${dateStr} · ${tA}–${tB} UTC`;
}

// ─── BinInspectionModal ───────────────────────────────────────────────────────

/**
 * Modal for inspecting a single time-bin.
 *
 * Props:
 *   isOpen            — boolean
 *   onClose           — () => void
 *   scoutId           — string
 *   authToken         — string
 *   classId           — string  (e.g. "vessels")
 *   classColor        — hex string (e.g. "#3989F9")
 *   binStart          — ISO string — initial bin start
 *   binEnd            — ISO string — initial bin end
 *   binMinutes        — number
 *   binsForNavigation — Array<{binStart, binEnd}> (same class, all with events)
 *   focused           — boolean — hide DetectionsZone, shrink modal (from jump button)
 *   pinnedEventAt     — ISO string — pre-select this event on open
 */
export default function BinInspectionModal({
  isOpen,
  onClose,
  scoutId,
  authToken,
  classId,
  classColor = "#5F5E5A",
  binStart: initialBinStart,
  binEnd:   initialBinEnd,
  binMinutes = 15,
  binsForNavigation = [],
  focused = false,
  pinnedEventAt = null,
  // Site (multi-deployment) mode — when provided, the modal fetches via the
  // Site bulk endpoint, renders the beeswarm + deployment legend instead of
  // the strip chart, and filters the events list by `depFilter`.
  siteContext,
  multiDeployment = false,
}) {
  const className = getCategoryLabel(classId);
  const isMulti = Boolean(multiDeployment && siteContext);

  // ── Navigation state ──────────────────────────────────────────────────────
  const [currentBinStart, setCurrentBinStart] = useState(initialBinStart);
  const [currentBinEnd,   setCurrentBinEnd]   = useState(initialBinEnd);
  const pinnedOnceRef = useRef(pinnedEventAt);

  // Deployment isolation filter — owned at the modal level so it survives
  // bin prev/next navigation. Only used in multi-deployment mode.
  const [depFilter, setDepFilter] = useState(null);

  // Reset nav + pinned state whenever modal opens with new props
  useEffect(() => {
    if (isOpen) {
      setCurrentBinStart(initialBinStart);
      setCurrentBinEnd(initialBinEnd);
      pinnedOnceRef.current = pinnedEventAt;
      setDepFilter(null);
    }
  }, [isOpen, initialBinStart, initialBinEnd, pinnedEventAt]);

  const navIndex = useMemo(
    () => binsForNavigation.findIndex((b) => b.binStart === currentBinStart),
    [binsForNavigation, currentBinStart],
  );
  const canGoPrev = navIndex > 0;
  const canGoNext = navIndex >= 0 && navIndex < binsForNavigation.length - 1;
  const navTotal  = binsForNavigation.length;

  const goPrev = useCallback(() => {
    if (!canGoPrev) return;
    const prev = binsForNavigation[navIndex - 1];
    setCurrentBinStart(prev.binStart);
    setCurrentBinEnd(prev.binEnd);
    pinnedOnceRef.current = null;
  }, [canGoPrev, binsForNavigation, navIndex]);

  const goNext = useCallback(() => {
    if (!canGoNext) return;
    const next = binsForNavigation[navIndex + 1];
    setCurrentBinStart(next.binStart);
    setCurrentBinEnd(next.binEnd);
    pinnedOnceRef.current = null;
  }, [canGoNext, binsForNavigation, navIndex]);

  // Keyboard: ← / → navigate; Escape handled by headlessui
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === "ArrowLeft")  goPrev();
      if (e.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, goPrev, goNext]);

  // ── Data fetching ─────────────────────────────────────────────────────────
  // Scout path — single hydrotwin.
  const scoutQuery = useQuery({
    queryKey: ["binInspection", scoutId, classId, currentBinStart, currentBinEnd],
    queryFn: ({ signal }) =>
      fetchDetectionsBinInspection(
        scoutId, currentBinStart, currentBinEnd, classId, authToken, signal,
      ),
    enabled:
      !isMulti && isOpen && Boolean(scoutId && authToken && currentBinStart && classId),
    staleTime: 60_000,
  });

  // Site path — bulk fan-out + flatten.
  const siteQuery = useSiteDetectionsBinInspection(
    isMulti && isOpen ? siteContext.siteId : null,
    isMulti && isOpen ? siteContext.htIds : [],
    isMulti && isOpen ? currentBinStart : null,
    isMulti && isOpen ? currentBinEnd : null,
    isMulti && isOpen ? classId : null,
  );
  const flattenedSite = useMemo(
    () => (isMulti ? flattenBinInspectionSeries(siteQuery.series) : null),
    [isMulti, siteQuery.series],
  );

  const data = isMulti ? flattenedSite : scoutQuery.data;
  const isLoading = isMulti ? siteQuery.isLoading : scoutQuery.isLoading;
  const error = isMulti ? siteQuery.error : scoutQuery.error;

  // ── Derived stats ─────────────────────────────────────────────────────────
  // All events from the response (unfiltered) — drives summary stats so they
  // stay stable as the user toggles deployment isolation.
  const allEvents = useMemo(() => data?.events ?? [], [data]);
  // depFilter (multi mode only) — the chart fades non-matching dots; the
  // events list and the auto-selected event are hard-filtered.
  const events = useMemo(() => {
    if (!isMulti || depFilter == null) return allEvents;
    return allEvents.filter((e) => e.htId === depFilter);
  }, [isMulti, depFilter, allEvents]);
  const peakPct   = allEvents.reduce((m, e) => Math.max(m, e.intensityPercentage || 0), 0);
  const peakSpl   = allEvents.reduce((m, e) => (e.splDb != null ? Math.max(m, e.splDb) : m), null);
  const eventCount = allEvents.length;
  const hasAcoustic = data?.acousticAvailable ?? false;

  // ── Selected event ────────────────────────────────────────────────────────
  const [selectedEvent, setSelectedEvent] = useState(null);

  useEffect(() => {
    // Pick the auto-selected event from the (filtered) events list so the
    // acoustic viewer honours the active deployment isolation in multi mode.
    if (!events?.length) { setSelectedEvent(null); return; }
    const acoustic = events.filter((e) => e.audioUrl);
    if (!acoustic.length) { setSelectedEvent(null); return; }

    // Honour pinnedEventAt only on first render of this bin.
    if (pinnedOnceRef.current) {
      const pinned = acoustic.find((e) => e.ingestedAt === pinnedOnceRef.current);
      if (pinned) { setSelectedEvent(pinned); return; }
    }
    // Default: latest ingestedAt among acoustic events.
    const latest = acoustic.reduce(
      (acc, ev) =>
        new Date(ev.ingestedAt).getTime() > new Date(acc.ingestedAt).getTime() ? ev : acc,
      acoustic[0],
    );
    setSelectedEvent(latest);
  }, [events]);

  const binStartMs = useMemo(
    () => (currentBinStart ? new Date(currentBinStart).getTime() : 0),
    [currentBinStart],
  );
  const binEndMs = useMemo(
    () => (currentBinEnd ? new Date(currentBinEnd).getTime() : 0),
    [currentBinEnd],
  );

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-[80]" onClose={onClose}>
        {/* Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50 backdrop-blur-[3px] dark:bg-black/70" />
        </Transition.Child>

        {/* Modal container */}
        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-16 768:p-24">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-[0.97]"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-[0.97]"
            >
              <Dialog.Panel
                className={`
                  relative flex w-full flex-col overflow-hidden rounded-[12px]
                  border border-grey200 bg-surface shadow-[0_16px_48px_rgba(0,0,0,0.22)]
                  dark:border-grey300 dark:shadow-[0_16px_64px_rgba(0,0,0,0.5)]
                  ${focused ? "max-w-[820px]" : "max-w-[1180px]"}
                  max-h-[calc(100vh-64px)]
                `}
              >
                {/* ── Header ─────────────────────────────────────────── */}
                <div className="flex flex-col gap-10 border-b border-grey200 bg-grey100 px-20 py-16 768:px-28 dark:border-grey300">
                  {/* Eyebrow row */}
                  <div className="flex items-center justify-between gap-12">
                    <div className="flex min-w-0 items-center gap-8 font-mono text-[10px] uppercase tracking-[0.15em] text-textSecondary">
                      <span>Window Inspection</span>
                      <span className="text-grey300" aria-hidden>·</span>
                      <span>{formatBinWidthLabel(binMinutes)} window</span>
                      <span className="text-grey300" aria-hidden>·</span>
                      <span
                        className="rounded-[3px] px-6 py-2 font-mono text-[10px] font-medium uppercase tracking-[0.1em]"
                        style={{
                          background: `${classColor}22`,
                          color: classColor,
                          border: `1px solid ${classColor}55`,
                        }}
                      >
                        {className}
                      </span>
                    </div>

                    {/* Navigation + Close */}
                    <div className="flex flex-shrink-0 items-center gap-6">
                      {navTotal > 0 && (
                        <>
                          <NavBtn
                            onClick={goPrev}
                            disabled={!canGoPrev}
                            aria-label="Previous bin"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
                              <path d="M15 18l-6-6 6-6" />
                            </svg>
                          </NavBtn>
                          <span className="font-mono text-[11px] tabular-nums text-textSecondary">
                            {navIndex >= 0 ? navIndex + 1 : "—"} / {navTotal}
                          </span>
                          <NavBtn
                            onClick={goNext}
                            disabled={!canGoNext}
                            aria-label="Next bin"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
                              <path d="M9 18l6-6-6-6" />
                            </svg>
                          </NavBtn>
                        </>
                      )}
                      <button
                        type="button"
                        onClick={onClose}
                        className="ml-4 flex h-30 w-30 items-center justify-center rounded-[6px] border border-grey300 bg-transparent text-textSecondary transition-colors duration-150 hover:border-grey400 hover:text-textPrimary dark:border-grey200"
                        aria-label="Close"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
                          <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Title row */}
                  <div>
                    <Dialog.Title className="font-sans text-[20px] font-normal leading-tight text-textPrimary 768:text-[22px]">
                      <span style={{ color: classColor }}>{className}</span>
                      {" "}
                      <span className="font-mono text-[13px] font-normal tracking-[0.02em] text-textSecondary">
                        {fmtUtcRange(currentBinStart, currentBinEnd)}
                      </span>
                    </Dialog.Title>
                  </div>
                </div>

                {/* ── Stats row ───────────────────────────────────────── */}
                <div className="grid grid-cols-3 divide-x divide-grey200 border-b border-grey200 dark:divide-grey300 dark:border-grey300">
                  <StatCell label="Peak Intensity">
                    <span style={{ color: classColor }}>
                      {Math.round(peakPct)}%
                    </span>
                  </StatCell>
                  <StatCell label="Events">
                    {eventCount}
                  </StatCell>
                  <StatCell label="Peak SPL">
                    {peakSpl != null ? `${Number(peakSpl).toFixed(1)} dB` : "—"}
                  </StatCell>
                </div>

                {/* ── Scrollable body ──────────────────────────────────── */}
                <div className="flex-1 overflow-y-auto">
                  {isLoading && (
                    <div className="flex h-[240px] items-center justify-center">
                      <div className="flex flex-col items-center gap-10">
                        <div className="h-8 w-8 animate-spin rounded-full border-2 border-grey300 border-t-primary" />
                        <span className="font-mono text-[12px] text-textSecondary">
                          Loading bin data…
                        </span>
                      </div>
                    </div>
                  )}

                  {error && (
                    <div className="flex h-[160px] items-center justify-center">
                      <p className="font-mono text-[12px] text-error">
                        {error.message || "Could not load bin data."}
                      </p>
                    </div>
                  )}

                  {data && (
                    <>
                      {/* ── Detections Zone ─────────────────────────────────
                            Hidden only when focused=true (jump-from-recent mode).
                            • Single-event bins: events table only (no chart).
                            • Multi-event bins:  strip chart + events table.
                      ──────────────────────────────────────────────────── */}
                      {!focused && (
                        <>
                          <div
                            className={`grid grid-cols-1 gap-20 px-20 py-20 768:px-28 ${
                              allEvents.length > 1 ? "768:grid-cols-[1.4fr_1fr]" : ""
                            }`}
                          >
                            {/* Left: chart — beeswarm (multi-deployment) or strip chart (single).
                                Hidden when there's only a single event. */}
                            {allEvents.length > 1 && (
                              <div className="min-w-0">
                                <div className="mb-10 flex items-center justify-between">
                                  <SectionLabel>Raw Detection Distribution</SectionLabel>
                                  <span className="font-mono text-[10px] text-primary">
                                    {eventCount} events
                                    {isMulti && depFilter != null && (
                                      <> · isolating <strong>{depFilter}</strong></>
                                    )}
                                  </span>
                                </div>
                                {isMulti ? (
                                  <BinInspectionBeeswarmChart
                                    events={allEvents}
                                    selectedEvent={selectedEvent}
                                    scopedHydrotwins={siteContext.scopedHydrotwins}
                                    depFilter={depFilter}
                                    binStartMs={binStartMs}
                                    binEndMs={binEndMs}
                                    onSelectEvent={setSelectedEvent}
                                  />
                                ) : (
                                  <BinInspectionStripChart
                                    events={events}
                                    selectedEvent={selectedEvent}
                                    classColor={classColor}
                                    binStartMs={binStartMs}
                                    binEndMs={binEndMs}
                                    onSelectEvent={setSelectedEvent}
                                  />
                                )}
                              </div>
                            )}

                            {/* Right: events list (always shown). depFilter, when set,
                                hard-filters the rows. */}
                            <div className="min-w-0">
                              <div className="mb-10">
                                <SectionLabel>Detection Events</SectionLabel>
                              </div>
                              <BinInspectionEventsList
                                events={events}
                                selectedEvent={selectedEvent}
                                onSelectEvent={setSelectedEvent}
                                scopedHydrotwins={
                                  isMulti ? siteContext.scopedHydrotwins : undefined
                                }
                              />
                            </div>
                          </div>

                          {/* Deployment legend — only in multi-deployment mode */}
                          {isMulti && allEvents.length > 0 && (
                            <BinInspectionDeploymentLegend
                              events={allEvents}
                              scopedHydrotwins={siteContext.scopedHydrotwins}
                              depFilter={depFilter}
                              onDepFilterChange={setDepFilter}
                            />
                          )}
                        </>
                      )}
                    </>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function NavBtn({ children, disabled, onClick, ...rest }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-30 w-30 items-center justify-center rounded-[6px] border border-grey300 bg-transparent text-textSecondary transition-colors duration-150 hover:border-grey400 hover:text-textPrimary disabled:cursor-not-allowed disabled:opacity-35 dark:border-grey200"
      {...rest}
    >
      {children}
    </button>
  );
}

function StatCell({ label, children }) {
  return (
    <div className="flex flex-col gap-4 px-20 py-14 768:px-28">
      <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-textSecondary">
        {label}
      </span>
      <div className="font-mono text-[18px] font-medium tabular-nums text-textPrimary 768:text-[20px]">
        {children}
      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-textSecondary">
      {children}
    </span>
  );
}
