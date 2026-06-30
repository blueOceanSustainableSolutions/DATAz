import { NavigationIcon } from "@/components/Icons";
import { cn } from "@/lib/classnames";
import { forwardRef } from "react";

/**
 *
 * @param {boolean} open
 * @param {Object} position
 * @param {number} position.x
 * @param {number} position.y
 * @param {string} extraClass
 * @returns JSX.Element|null
 */

export const ChartTooltip = forwardRef(
  ({ open, position, extraClass, children }, ref) => {
    if (!open) return null;

    return (
      <div
        ref={ref}
        className={cn(
          "absolute shadow-md bg-gray-800 text-white border p-8 rounded-8 copy-small flex flex-col gap-6 text-nowrap",
          extraClass,
        )}
        style={{ left: position.x, top: position.y }}
      >
        {children}
      </div>
    );
  },
);
ChartTooltip.displayName = "ChartTooltip";

export const ChartTooltipTitle = ({ children }) => {
  return <div className="text-gray-300 mb-4">{children}</div>;
};

export const ChartTooltipItem = ({ color, label, value, unit, highlight, dim }) => {
  const isDegrees = unit === "degrees";
  const opacity = highlight ? 1 : dim ? 0.6 : 1;
  const weight = highlight ? "font-semibold" : "font-normal";
  return (
    <div
      className={cn("flex gap-8 items-center", weight)}
      style={{ opacity }}
    >
      {!isDegrees && (
        <div
          className="rounded-4"
          style={{
            background: color,
            width: highlight ? 12 : 10,
            height: highlight ? 5 : 4,
          }}
        ></div>
      )}
      {isDegrees && (
        <NavigationIcon
          style={{
            transform: `rotate(${parseInt(value || 0) + 180}deg)`,
            color: color,

          }}
        />
      )}
      {label}: {value} {isDegrees ? "°" : unit}
    </div>
  );
};
