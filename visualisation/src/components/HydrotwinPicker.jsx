import { useState, useRef, useEffect } from "react";
import HydrotwinTypeBadge from "@/components/HydrotwinTypeBadge";
import { OutlineButton, GhostPrimaryButton, ListItemButton } from "@/components/Buttons";
import { getOverlayColor } from "@/constants/hydrotwinTypeRegistry";
import { ChevronDown } from "@/components/Icons";

/**
 * Dropdown control that lets a chart card select which hydrotwins to overlay.
 *
 * Props
 *   hydrotwins    Hydrotwin[]       scoped to the card's participatesIn filter
 *   selectedIds   Set<string>       currently selected htIds
 *   onChange      (Set<string>) => void
 *   mode          'single' | 'multi'
 */
export default function HydrotwinPicker({
  hydrotwins,
  selectedIds,
  onChange,
  mode = "multi",
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const toggle = (htId) => {
    if (mode === "single") {
      onChange(new Set([htId]));
      setOpen(false);
      return;
    }
    const next = new Set(selectedIds);
    if (next.has(htId)) next.delete(htId);
    else next.add(htId);
    onChange(next);
  };

  const label = (() => {
    if (selectedIds.size === 0) return "None";
    if (mode === "single") return [...selectedIds][0] ?? "Select…";
    if (selectedIds.size === hydrotwins.length) return "All";
    return `${selectedIds.size} of ${hydrotwins.length}`;
  })();

  return (
    <div ref={ref} className="relative">
      <OutlineButton
        size="small"
        onClick={() => setOpen((v) => !v)}
        extraClass="gap-6 whitespace-nowrap"
      >
        {label}
        <ChevronDown
          extraClass={`transition-transform duration-150 ${open ? "-rotate-180" : ""}`}
        />
      </OutlineButton>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-4 rounded-8 border border-grey300 bg-surface drop-shadow-default"
          style={{ minWidth: 200 }}
        >
          {mode === "multi" && hydrotwins.length > 1 && (
            <div className="flex gap-12 border-b border-grey300 px-12 py-8">
              <GhostPrimaryButton
                onClick={() => onChange(new Set(hydrotwins.map((h) => h.htId)))}
                extraClass="!copy-extrasmall"
              >
                All
              </GhostPrimaryButton>
              <GhostPrimaryButton
                onClick={() => onChange(new Set())}
                extraClass="!copy-extrasmall"
              >
                None
              </GhostPrimaryButton>
            </div>
          )}

          <div className="max-h-240 overflow-y-auto py-4">
            {hydrotwins.map((ht) => {
              const checked = selectedIds.has(ht.htId);
              const color = getOverlayColor({ htId: ht.htId, scopedHydrotwins: hydrotwins });

              return (
                <ListItemButton key={ht.htId} onClick={() => toggle(ht.htId)}>
                  {mode === "multi" && (
                    <span
                      className="flex items-center justify-center rounded-4 border shrink-0"
                      style={{
                        width: 14,
                        height: 14,
                        background: checked ? color : "transparent",
                        borderColor: checked ? color : "var(--grey-300)",
                      }}
                    >
                      {checked && (
                        <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                          <path
                            d="M1 3.5l2.5 2.5 4.5-5"
                            stroke="white"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </span>
                  )}

                  <HydrotwinTypeBadge htId={ht.htId} status={ht.status} size={12} />

                  <div className="min-w-0 flex-1">
                    <p className="copy-extrasmall text-textPrimary truncate">{ht.htId}</p>
                    {ht.location && (
                      <p className="copy-extrasmall text-textSecondary truncate">
                        {ht.location}
                      </p>
                    )}
                  </div>

                  {mode === "single" && checked && (
                    <svg className="ml-auto shrink-0" width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M2 6l3 3 5-6"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </ListItemButton>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
