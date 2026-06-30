import { useRef, useEffect, useCallback } from "react";
import HydrotwinCard from "@/components/HydrotwinCard";
import { InfoCircleIcon } from "@/components/Icons";

/**
 * HydrotwinRail — scrollable column of HydrotwinCards with scroll-fade shadows.
 * Matches the design's .hts-rail-scroll + .hts-rail-shadow pattern.
 *
 * Props:
 *   hydrotwins      Array<HydrotwinDTO>
 *   selectedHtId    string | null
 *   onSelect        (htId) => void
 *   realtimeByHtId  Map<string, RealtimeData> | null
 */
function CardSkeleton() {
  return (
    <div style={{
      borderRadius: 10,
      border: "0.5px solid var(--grey-300)",
      borderLeft: "3px solid transparent",
      padding: "12px 14px",
      background: "var(--surface)",
    }}>
      {/* Identity row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <div style={{ width: 26, height: 26, borderRadius: "50%", background: "var(--grey-300)" }} className="animate-pulse" />
        <div style={{ flex: 1 }}>
          <div style={{ height: 12, width: 80, borderRadius: 4, background: "var(--grey-300)", marginBottom: 5 }} className="animate-pulse" />
          <div style={{ height: 10, width: 56, borderRadius: 4, background: "var(--grey-200)" }} className="animate-pulse" />
        </div>
        <div style={{ height: 22, width: 52, borderRadius: 20, background: "var(--grey-300)" }} className="animate-pulse" />
      </div>
      {/* Core row */}
      <div style={{ height: 52, borderRadius: 6, background: "var(--grey-200)", marginBottom: 10 }} className="animate-pulse" />
      {/* Action row */}
      <div style={{ height: 36, borderRadius: 7, background: "var(--grey-200)" }} className="animate-pulse" />
    </div>
  );
}

export default function HydrotwinRail({
  hydrotwins = [],
  isLoading = false,
  selectedHtId,
  onSelect,
  onSpotterClick,
  realtimeByHtId,
  hasAcoustics = true,
}) {
  const scrollRef = useRef(null);
  const shadowTopRef = useRef(null);
  const shadowBotRef = useRef(null);

  const updateShadows = useCallback(() => {
    const el = scrollRef.current;
    const top = shadowTopRef.current;
    const bot = shadowBotRef.current;
    if (!el || !top || !bot) return;

    const atTop = el.scrollTop <= 2;
    const atBottom = el.scrollHeight - el.clientHeight - el.scrollTop <= 2;
    const canScroll = el.scrollHeight > el.clientHeight;

    top.style.opacity = atTop ? "0" : "1";
    bot.style.opacity = (atBottom || !canScroll) ? "0" : "1";
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", updateShadows, { passive: true });
    window.addEventListener("resize", updateShadows);
    updateShadows();
    return () => {
      el.removeEventListener("scroll", updateShadows);
      window.removeEventListener("resize", updateShadows);
    };
  }, [updateShadows, hydrotwins]);

  if (isLoading || hydrotwins.length === 0) {
    return (
      <div style={{ height: "100%", overflowY: "auto", padding: "2px 4px 2px 0" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {isLoading
            ? Array.from({ length: 3 }, (_, i) => <CardSkeleton key={i} />)
            : (
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                height: "100%",
                minHeight: 240,
                padding: "24px 16px",
                textAlign: "center",
              }}>
                <InfoCircleIcon extraClass="w-32 text-grey400" />
                <div>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                    No hydrotwins at this site
                  </p>
                  <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    No devices are configured for this site.
                  </p>
                </div>
              </div>
            )}
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Top scroll shadow */}
      <div
        ref={shadowTopRef}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 16,
          background: "linear-gradient(to bottom, var(--surface), transparent)",
          pointerEvents: "none",
          zIndex: 2,
          opacity: 0,
          transition: "opacity 0.2s ease",
        }}
      />

      {/* Scrollable list */}
      <div
        ref={scrollRef}
        style={{
          height: "100%",
          overflowY: "auto",
          overflowX: "hidden",
          paddingRight: 4,
          scrollbarWidth: "thin",
          scrollbarColor: "var(--grey-300) transparent",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {hydrotwins.map((ht) => (
            <HydrotwinCard
              key={ht.htId}
              hydrotwin={ht}
              selected={ht.htId === selectedHtId}
              onClick={() => onSelect?.(ht.htId)}
              onSpotterClick={onSpotterClick ? () => onSpotterClick(ht.htId) : null}
              realtimeData={realtimeByHtId?.get(ht.htId) ?? null}
              hasAcoustics={hasAcoustics}
            />
          ))}
        </div>
      </div>

      {/* Bottom scroll shadow */}
      <div
        ref={shadowBotRef}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 16,
          background: "linear-gradient(to top, var(--surface), transparent)",
          pointerEvents: "none",
          zIndex: 2,
          opacity: 0,
          transition: "opacity 0.2s ease",
        }}
      />
    </>
  );
}
