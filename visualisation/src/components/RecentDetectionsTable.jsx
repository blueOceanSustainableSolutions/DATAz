import clsx from "clsx";
import {
  getCategoryColor,
  getCategoryHex,
  getCategoryLabel,
  formatExactUtcTimeSubline,
  formatTimeAgo,
  getSplDb,
} from "@/lib/detections";
import { getOverlayColor, getHydrotwinTypeKey } from "@/constants/hydrotwinTypeRegistry";

// ─── Absorbed sub-component ─────────────────────────────────────────────────

function RecentJumpButton({ className, onClick }) {
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex h-[26px] w-[26px] items-center justify-center rounded-[6px] border border-grey300 bg-transparent text-textSecondary transition-all duration-150",
        "hover:border-primary hover:bg-primarySelected hover:text-primary",
        "group-hover/row:border-primary group-hover/row:bg-primarySelected group-hover/row:text-primary",
        className,
      )}
      aria-label="Inspect detection"
      title="Inspect this detection's acoustic signature"
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
    >
      <svg
        width="11"
        height="11"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        aria-hidden
      >
        <path d="M7 17L17 7" />
        <path d="M7 7h10v10" />
      </svg>
    </button>
  );
}

const JUMP_BIN_MINUTES = 15;

function computeJumpBin(ingestedAt) {
  const tMs  = new Date(ingestedAt).getTime();
  if (!Number.isFinite(tMs)) return null;
  const binMs    = JUMP_BIN_MINUTES * 60 * 1000;
  const binStart = new Date(Math.floor(tMs / binMs) * binMs).toISOString();
  const binEnd   = new Date(Math.floor(tMs / binMs) * binMs + binMs).toISOString();
  return { binStart, binEnd };
}

export default function RecentDetectionsTable({
  rows,
  nowMs,
  onJumpClick,
  showJump = true,
  showHydrotwinColumn = false,
  scopedHydrotwins,
}) {
  if (!rows?.length) {
    return (
      <div className="px-32 py-32 text-center font-mono text-[13px] text-textSecondary">
        No detections matching this filter
      </div>
    );
  }

  return (
    <div className="max-h-[280px] overflow-x-auto overflow-y-auto" style={{ scrollbarWidth: "thin" }}>
      <table
        className={clsx(
          "w-full border-collapse text-[13px]",
          showHydrotwinColumn ? "min-w-[680px]" : "min-w-[560px]",
        )}
      >
        <thead className="sticky top-0 z-[1] bg-grey100">
          <tr>
            <Th>Timestamp</Th>
            {showHydrotwinColumn && <Th>Hydrotwin</Th>}
            <Th>Class</Th>
            <Th>Intensity</Th>
            <Th>SPL (dB)</Th>
            {showJump && <Th className="text-center"> </Th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const cat   = String(row.category || "").toLowerCase();
            const color = getCategoryColor(cat);
            const label = getCategoryLabel(cat);
            const pct   = Math.round(Number(row.intensityPercentage) || 0);
            const splN  = getSplDb(row);
            const spl   = splN != null ? splN.toFixed(1) : "—";
            const key   = `${row.fileId}-${row.ingestedAt}-${idx}`;
            const htId  = row.htId ?? null;
            const htColor = htId && scopedHydrotwins
              ? getOverlayColor({ htId, scopedHydrotwins })
              : null;
            const rowCanJump = getHydrotwinTypeKey(htId) !== "HT-S";

            const handleJump = () => {
              if (!onJumpClick) return;
              const bin = computeJumpBin(row.ingestedAt);
              if (!bin) return;
              onJumpClick({
                classId:      cat,
                classColor:   getCategoryHex(cat),
                binStart:     bin.binStart,
                binEnd:       bin.binEnd,
                binMinutes:   JUMP_BIN_MINUTES,
                binsForNavigation: [],
                focused:      true,
                pinnedEventAt: row.ingestedAt,
              });
            };

            return (
              <tr
                key={key}
                className="group/row cursor-pointer transition-colors duration-150 hover:bg-grey100"
              >
                <td className="w-[110px] border-b border-grey200 px-16 py-10 align-middle">
                  <div className="whitespace-nowrap font-mono text-[13px] text-textPrimary">
                    {formatTimeAgo(row.ingestedAt, nowMs)}
                  </div>
                  <div className="mt-[2px] font-mono text-[11px] text-textSecondary">
                    {formatExactUtcTimeSubline(row.ingestedAt)}
                  </div>
                </td>
                {showHydrotwinColumn && (
                  <td className="w-[120px] border-b border-grey200 px-16 py-10 align-middle font-mono text-[12px] text-textPrimary">
                    {htId ? (
                      <div className="flex items-center gap-6">
                        {htColor && (
                          <span
                            className="h-8 w-8 flex-shrink-0 rounded-full"
                            style={{ background: htColor }}
                            aria-hidden
                          />
                        )}
                        <span className="truncate">{htId}</span>
                      </div>
                    ) : (
                      <span className="text-textSecondary">—</span>
                    )}
                  </td>
                )}
                <td className="border-b border-grey200 px-16 py-10 align-middle font-medium text-textPrimary">
                  <div className="flex items-center gap-8">
                    <span
                      className="h-8 w-8 flex-shrink-0 rounded-full"
                      style={{ background: color }}
                      aria-hidden
                    />
                    {label}
                  </div>
                </td>
                <td className="w-[130px] border-b border-grey200 px-16 py-10 align-middle font-mono tabular-nums text-textPrimary">
                  <div className="inline-flex items-center gap-8">
                    <span>{pct}%</span>
                    <span className="inline-block h-4 w-[56px] overflow-hidden rounded-[2px] bg-grey200 shadow-[inset_0_0_0_0.5px_var(--grey-200)]">
                      <span
                        className="block h-full rounded-[2px]"
                        style={{
                          width: `${Math.min(100, Math.max(0, pct))}%`,
                          background: color,
                        }}
                      />
                    </span>
                  </div>
                </td>
                <td className="w-[80px] border-b border-grey200 px-16 py-10 align-middle font-mono tabular-nums text-textPrimary">
                  {spl}
                </td>
                {showJump && (
                  <td className="w-[50px] border-b border-grey200 px-16 py-10 text-center align-middle">
                    {rowCanJump && <RecentJumpButton onClick={handleJump} />}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className }) {
  return (
    <th
      className={clsx(
        "border-b border-grey200 px-16 py-10 text-left font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-textSecondary",
        className,
      )}
    >
      {children}
    </th>
  );
}
