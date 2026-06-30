import AtomChartCard from "@/components/ChartCard";
import ChartIcon from "@/components/ChartIcon";

/**
 * Molecule: standard chart card shell used by every ChartCardController on the
 * site page. Composes the existing ChartCard atom with a header row (icon +
 * title/subtitle + optional controls slot) and a body slot for the chart.
 *
 * By default the controls sit inline to the RIGHT of the header on every
 * breakpoint — matching the web layout. `stackControlsOnMobile` reverts to the
 * stacked layout (controls drop below the title under 768px); used by the SPL
 * cards whose band/percentile pickers are too wide to share the header row.
 */
export default function ChartCard({
  icon,
  title,
  subtitle,
  controls,
  stackControlsOnMobile = false,
  children,
}) {
  const headerClass = stackControlsOnMobile
    ? "flex flex-col gap-8 mb-12 768:mb-16 768:flex-row 768:items-start 768:justify-between"
    : "flex flex-row items-start justify-between gap-8 mb-12 768:mb-16";
  const controlsClass = stackControlsOnMobile
    ? "shrink-0 768:ml-auto 768:pl-8"
    : "shrink-0 ml-auto pl-8";

  return (
    <AtomChartCard>
      <div className={headerClass}>
        <div className="flex items-center gap-8 min-w-0">
          {icon && (
            <ChartIcon
              name={icon}
              size={24}
              extraClass="shrink-0 text-textSecondary"
            />
          )}
          <div className="min-w-0">
            <p className="copy-body font-semibold text-textPrimary leading-tight">
              {title}
            </p>
            {subtitle && (
              <p className="copy-extrasmall text-textSecondary mt-1">
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {controls && <div className={controlsClass}>{controls}</div>}
      </div>
      {children}
    </AtomChartCard>
  );
}
