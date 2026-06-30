import {
  HYDROTWIN_TYPE_REGISTRY,
  getHydrotwinTypeKey,
} from "@/constants/hydrotwinTypeRegistry";
import { STATUS_LABELS, STATUS_HEX } from "@/constants/statusConfig";

/**
 * Badge SVG matching the design's buildMarkerSVG:
 *   HT-S → circle, HT-C → rounded square, HT-V → rotated square (diamond)
 * Fill = status colour; stroke = white; letter = white.
 *
 * Props:
 *   htId      string  — used to derive type
 *   type      'HT-S'|'HT-C'|'HT-V'  — explicit override
 *   status    string
 *   size      number  — px (default 26)
 *   selected  boolean
 *   title     string?
 */

function resolveKey(status) {
  return status ? String(status).toLowerCase() : "";
}

function BadgeSVG({ shape, letter, stroke, fill, size }) {
  // 32x32 viewBox matching design, scaled to `size`
  const sw = 2.5;
  let inner = null;
  if (shape === "square") {
    inner = (
      <rect
        x="7" y="7" width="18" height="18" rx="2"
        fill={fill} stroke={stroke} strokeWidth={sw}
      />
    );
  } else if (shape === "triangle") {
    inner = (
      <polygon
        points="16,5 27,26 5,26"
        fill={fill} stroke={stroke} strokeWidth={sw} strokeLinejoin="round"
      />
    );
  } else {
    // circle (HT-S)
    inner = (
      <circle
        cx="16" cy="16" r="9"
        fill={fill} stroke={stroke} strokeWidth={sw}
      />
    );
  }
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      {inner}
      <text
        x="16" y="20"
        textAnchor="middle"
        fontSize="10"
        fontWeight="500"
        fill="white"
        fontFamily="-apple-system, sans-serif"
      >
        {letter}
      </text>
    </svg>
  );
}

export default function HydrotwinTypeBadge({
  htId,
  type,
  status,
  size = 26,
  selected = false,
  title,
}) {
  const resolvedType = type ?? getHydrotwinTypeKey(htId);
  const meta = resolvedType ? HYDROTWIN_TYPE_REGISTRY[resolvedType] : null;
  const shape = meta?.markerShape ?? "circle";

  // Letter is the suffix after "HT-" (S, C, V)
  const letter = resolvedType ? resolvedType.split("-")[1] ?? "?" : "?";

  const key = resolveKey(status);
  const stroke = STATUS_HEX[key] ?? "#b5b8b8";

  const statusLabel = STATUS_LABELS[key] ?? (status ?? "");
  const tip = title ?? (htId ? `${htId}${statusLabel ? ` · ${statusLabel}` : ""}` : statusLabel);

  return (
    <span
      title={tip}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        width: size,
        height: size,
        transition: "transform 0.15s",
        transform: selected ? "scale(1.15)" : "none",
      }}
    >
      <BadgeSVG shape={shape} letter={letter} stroke="white" fill={stroke} size={size} />
    </span>
  );
}
