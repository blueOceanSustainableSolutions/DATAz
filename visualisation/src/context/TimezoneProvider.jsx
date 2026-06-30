import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const TimezoneContext = createContext(null);

function getLocalOffsetMs() {
  return -(new Date().getTimezoneOffset() * 60_000);
}

/**
 * Compute UTC offset in ms for an IANA timezone string using Intl.
 * Returns 0 on server (SSR-safe) or if the zone is unknown.
 */
function getOffsetMsForZone(ianaZone) {
  if (typeof window === "undefined" || !ianaZone) return 0;
  try {
    const now = new Date();
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: ianaZone,
      year: "numeric", month: "numeric", day: "numeric",
      hour: "numeric", minute: "numeric", second: "numeric",
      hour12: false,
    }).formatToParts(now);
    const get = (type) =>
      parseInt(parts.find((p) => p.type === type)?.value ?? "0");
    const zoneMs = Date.UTC(
      get("year"), get("month") - 1, get("day"),
      get("hour") % 24, get("minute"), get("second"),
    );
    return zoneMs - Math.floor(now.getTime() / 1000) * 1000;
  } catch {
    return 0;
  }
}

function getGMTLabel(offsetMs) {
  if (offsetMs === 0) return "GMT+0";
  const totalMinutes = Math.abs(offsetMs) / 60_000;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const sign = offsetMs >= 0 ? "+" : "-";
  return minutes > 0
    ? `GMT${sign}${hours}:${String(minutes).padStart(2, "0")}`
    : `GMT${sign}${hours}`;
}

export function TimezoneProvider({ children }) {
  const [mode, setModeState] = useState(() => {
    if (typeof window === "undefined") return "local";
    return localStorage.getItem("ht_timezone_mode") ?? "local";
  });

  // Start at 0 so server and first client render match (avoids hydration mismatch).
  const [localOffsetMs, setLocalOffsetMs] = useState(0);
  useEffect(() => {
    setLocalOffsetMs(getLocalOffsetMs());
  }, []);

  // IANA timezone of the deployed scout (e.g. "Atlantic/Madeira").
  // Set by the scout page on mount; null on all other pages.
  const [deploymentIana, setDeploymentIana] = useState(null);
  const deploymentOffsetMs = useMemo(
    () => getOffsetMsForZone(deploymentIana),
    [deploymentIana],
  );

  const offsetMs =
    mode === "utc" ? 0
    : mode === "deployment" ? deploymentOffsetMs
    : localOffsetMs;

  const localGmtLabel = useMemo(() => getGMTLabel(localOffsetMs), [localOffsetMs]);
  const deploymentGmtLabel = useMemo(
    () => getGMTLabel(deploymentOffsetMs),
    [deploymentOffsetMs],
  );
  const gmtLabel =
    mode === "utc" ? "UTC"
    : mode === "deployment" ? deploymentGmtLabel
    : localGmtLabel;

  const axisLabel =
    mode === "utc" ? "Time [UTC]"
    : mode === "deployment" ? `Time [Hydrotwin (${deploymentGmtLabel})]`
    : `Time [Local (${localGmtLabel})]`;

  const setMode = (newMode) => {
    setModeState(newMode);
    if (typeof window !== "undefined") {
      localStorage.setItem("ht_timezone_mode", newMode);
    }
  };

  const setDeploymentTimezone = useCallback((ianaZone) => {
    setDeploymentIana(ianaZone ?? null);
  }, []);

  const shiftToDisplay = useCallback(
    (input) => {
      if (!input) return input;
      if (offsetMs === 0) {
        return typeof input === "string" ? input : input.toISOString();
      }
      const ms = new Date(input).getTime() + offsetMs;
      return new Date(ms).toISOString().slice(0, -1);
    },
    [offsetMs],
  );

  const value = useMemo(
    () => ({
      mode, setMode,
      offsetMs, axisLabel,
      gmtLabel, deploymentGmtLabel,
      deploymentTimezone: deploymentIana,
      setDeploymentTimezone,
      shiftToDisplay,
    }),
    [mode, offsetMs, axisLabel, gmtLabel, localGmtLabel, deploymentGmtLabel, deploymentIana, setDeploymentTimezone, shiftToDisplay],
  );

  return (
    <TimezoneContext.Provider value={value}>{children}</TimezoneContext.Provider>
  );
}

export function useTimezone() {
  const ctx = useContext(TimezoneContext);
  if (!ctx) {
    throw new Error("useTimezone must be used within a TimezoneProvider");
  }
  return ctx;
}
