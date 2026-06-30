import { useState, useEffect, useRef, useMemo } from "react";
import { DayPicker } from "react-day-picker";
import { CalendarIcon, InfoOutlinedIcon } from "@/components/Icons";
import "react-day-picker/dist/style.css";
import { formatDateToDDMMYYYY, dateKeyUTC } from "@/lib/date";
import { useTimezone } from "@/context/TimezoneProvider";

const MAX_DAYS_DEFAULT = 30; // HT-S
const MAX_DAYS_HT_C = 7; // HT-C / SCOUT-C

// Define parseDate function outside the component to avoid reference issues
const parseDate = (dateStr) => {
  // If dateStr is already a Date object, return it
  if (dateStr instanceof Date) {
    return dateStr;
  }

  // Handle special case for dynamic dates
  if (dateStr === "currentDate") {
    return new Date(); // Return today's date
  }

  try {
    // Handle ISO format dates (YYYY-MM-DDTHH:MM:SS.sssZ)
    if (dateStr.includes("T")) {
      return new Date(dateStr);
    }

    // Handle both slash and hyphen formats (DD/MM/YYYY or DD-MM-YYYY)
    const parts = dateStr.includes("/")
      ? dateStr.split("/")
      : dateStr.split("-");

    // Check if it's YYYY-MM-DD format (parts[0] would be 4 digits)
    if (parts[0].length === 4) {
      const [year, month, day] = parts.map(Number);
      if (isNaN(day) || isNaN(month) || isNaN(year)) {
        console.warn(`Invalid date parts in: ${dateStr}`);
        return new Date(); // Fallback to today's date
      }
      return new Date(Date.UTC(year, month - 1, day));
    } else {
      // DD/MM/YYYY or DD-MM-YYYY format
      const [day, month, year] = parts.map(Number);
      if (isNaN(day) || isNaN(month) || isNaN(year)) {
        console.warn(`Invalid date parts in: ${dateStr}`);
        return new Date(); // Fallback to today's date
      }
      return new Date(Date.UTC(year, month - 1, day));
    }
  } catch (error) {
    console.error(`Error parsing date: ${dateStr}`, error);
    return new Date(); // Fallback to today's date
  }
};

const isHtCDevice = (id) =>
  id && String(id).toLowerCase().match(/^(ht-c|scout-c)-/);

const CustomDatepickerScoutPage = ({
  defaultDateStart,
  defaultDateEnd,
  handleDatesApply,
  enabledDates = null,
  scoutId = null,
  isLoading = false,
  openUpward = false,
}) => {
  const { mode: tzMode, setMode: setTzMode, deploymentTimezone } = useTimezone();
  const datepickerRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);
  const maxDays = useMemo(
    () => (isHtCDevice(scoutId) ? MAX_DAYS_HT_C : MAX_DAYS_DEFAULT),
    [scoutId],
  );
  const [range, setRange] = useState(() => {
    if (defaultDateStart && defaultDateEnd) {
      return {
        from: parseDate(defaultDateStart),
        to: parseDate(defaultDateEnd),
      };
    }
    return undefined;
  });

  // Sync Internal Range When Applied Range Changes From Parent (e.g. Default Range Click)
  useEffect(() => {
    if (defaultDateStart && defaultDateEnd) {
      setRange({
        from: parseDate(defaultDateStart),
        to: parseDate(defaultDateEnd),
      });
    }
  }, [defaultDateStart, defaultDateEnd]);

  // Check If The Next Range Is The Same As The Applied Range
  const isSameRangeAsApplied = (nextFrom, nextTo) => {
    const appliedFrom = parseDate(defaultDateStart);
    const appliedTo = parseDate(defaultDateEnd);

    return (
      dateKeyUTC(nextFrom) === dateKeyUTC(appliedFrom) &&
      dateKeyUTC(nextTo) === dateKeyUTC(appliedTo)
    );
  };

  // Function to find the most recent enabled date range
  const getMostRecentEnabledDateMonth = () => {
    // Default to today's date
    const today = new Date();

    // If we have default dates, use those
    if (defaultDateStart) {
      return parseDate(defaultDateStart);
    }

    return today;
  };

  const disabledDays = useMemo(() => {
    if (enabledDates && enabledDates.length > 0) {
      return {};
    }

    const now = new Date();
    const tomorrow = new Date(
      Date.UTC(
        now.getUTCFullYear(),
        now.getUTCMonth(),
        now.getUTCDate() + 1,
      ),
    );

    return { after: tomorrow };
  }, [enabledDates]);

  const toggleCalendar = () => {
    setIsOpen(!isOpen);
  };

  const datepickerText = () => {
    if (!range || (!range.from && !range.to)) {
      try {
        return `${formatDateToDDMMYYYY(defaultDateStart) || ""} - ${
          formatDateToDDMMYYYY(defaultDateEnd) || ""
        }`;
      } catch (error) {
        console.error("Error formatting default dates", error);
        return "Select dates";
      }
    }

    try {
      return `${formatDateToDDMMYYYY(range?.from)} - ${formatDateToDDMMYYYY(
        range?.to,
      )}`;
    } catch (error) {
      console.error("Error formatting range dates", error);
      return "Select dates";
    }
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        datepickerRef.current &&
        !datepickerRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside, true);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside, true);
    };
  }, []);

  return (
    <div ref={datepickerRef} className="relative w-full min-w-0 540:min-w-340 inline-block">
      <button
        onClick={toggleCalendar}
        className="w-full px-16 pr-40 py-13 rounded-8 bg-surface border border-grey300 flex items-center"
      >
        <span className="copy-body">{datepickerText()}</span>
        <span className="absolute right-16 top-1/2 -translate-y-1/2 flex items-center justify-center w-20 h-20">
          {isLoading ? (
            <svg width="22" height="22" viewBox="0 0 18 18" className="animate-spin">
              <circle cx="9" cy="9" r="7" stroke="#E0E0E0" strokeWidth="2" fill="none" />
              <circle cx="9" cy="9" r="7" stroke="#333" strokeWidth="2" fill="none"
                strokeLinecap="round" strokeDasharray="44" strokeDashoffset="32" />
            </svg>
          ) : (
            <CalendarIcon />
          )}
        </span>
      </button>
      {isOpen && (
        <div className={`absolute left-0 540:left-1/2 540:-translate-x-1/2 w-full z-10 bg-surface rounded-8 drop-shadow-default ${openUpward ? "bottom-full mb-2" : "mt-2"}`}>
          <div className="flex flex-col 375:flex-row 375:items-center justify-between gap-8 px-16 768:px-24 pt-16 768:pt-24">
            <span className="copy-small text-grey500">Timezone</span>
            <div className="flex w-full 375:w-auto rounded-8 border border-grey200 overflow-hidden">
              <button
                onClick={() => setTzMode("local")}
                className={`flex-1 px-10 768:px-12 py-6 copy-small transition-colors ${tzMode === "local" ? "bg-textPrimary text-surface" : "bg-surface text-grey500 hover:bg-grey100"}`}
              >
                Local
              </button>
              {deploymentTimezone && (
                <button
                  onClick={() => setTzMode("deployment")}
                  className={`flex-1 px-10 768:px-12 py-6 copy-small transition-colors ${tzMode === "deployment" ? "bg-textPrimary text-surface" : "bg-surface text-grey500 hover:bg-grey100"}`}
                >
                  Hydrotwin
                </button>
              )}
              <button
                onClick={() => setTzMode("utc")}
                className={`flex-1 px-10 768:px-12 py-6 copy-small transition-colors ${tzMode === "utc" ? "bg-textPrimary text-surface" : "bg-surface text-grey500 hover:bg-grey100"}`}
              >
                UTC
              </button>
            </div>
          </div>
          <DayPicker
            timeZone="UTC"
            mode="range"
            selected={range}
            onSelect={(newRange) => {
              if (!newRange) {
                setRange(undefined);
                return;
              }

              if (!newRange.from || !newRange.to) {
                setRange(newRange);
                return;
              }

              try {
                const toStartOfDay = (date) => {
                  if (!date) return null;
                  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 0, 0, 0, 0));
                };
                const toEndOfDay = (date) => {
                  if (!date) return null;
                  const eod = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 23, 59, 59, 999));
                  // Never go beyond now — no point fetching future data
                  return eod > new Date() ? new Date() : eod;
                };

                // Check if the date range is within the allowed limit based on scout ID
                const fromDate = toStartOfDay(newRange.from);
                const toDate = toEndOfDay(newRange.to);

                // Calculate the difference in milliseconds and convert to days
                const daysDifference = Math.round(
                  (toDate - fromDate) / (1000 * 60 * 60 * 24),
                );

                // If more than the maximum allowed days, adjust the end date
                if (daysDifference >= maxDays) {
                  const adjustedEndDate = new Date(fromDate);
                  adjustedEndDate.setUTCDate(
                    fromDate.getUTCDate() + (maxDays - 1),
                  );

                  const fixedRange = {
                    from: fromDate,
                    to: adjustedEndDate,
                  };

                  setRange(fixedRange);
                  if (!isSameRangeAsApplied(fixedRange.from, fixedRange.to)) {
                    handleDatesApply(fixedRange.from, fixedRange.to);
                  }
                } else {
                  const fixedRange = {
                    from: fromDate,
                    to: toDate,
                  };
                  setRange(fixedRange);
                  if (!isSameRangeAsApplied(fixedRange.from, fixedRange.to)) {
                    handleDatesApply(fixedRange.from, fixedRange.to);
                  }
                }
              } catch (error) {
                console.error("Error setting date range", error);
              }
            }}
            numberOfMonths={1}
            disabled={disabledDays}
            defaultMonth={getMostRecentEnabledDateMonth()}
            className="custom-datepicker copy-small"
            footer={
              <div className="flex flex-col p-12 border-t border-grey200">
                <div className="flex items-center justify-center gap-8 p-8 bg-blue-100 rounded-8">
                  <InfoOutlinedIcon extraClass="text-blue-700 w-24" />
                  <span className="text-sm font-medium text-blue-700 copy-small">
                    Maximum Date Range:{" "}
                    <span className="font-bold">{maxDays} days</span>
                  </span>
                </div>
              </div>
            }
          />
        </div>
      )}
    </div>
  );
};

export default CustomDatepickerScoutPage;
