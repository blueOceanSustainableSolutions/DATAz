import cn from "clsx";

const ALERT_VARIANTS = {
  neutral: "border-gray-300 bg-surface text-textPrimary",
  success: "border-green-300 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400",
  error: "border-red-100 bg-red-50 text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400",
  info: "border-blue-100 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-400",
};

/**
 * @param {string} variant "neutral" | "success" | "error"
 * @param {string} extraClass
 * @returns {JSX.Element}
 */

export const Alert = ({ variant = "neutral", className = "", children }) => {
  const styles = ALERT_VARIANTS[variant] || ALERT_VARIANTS.neutral;
  return (
    <div
      className={cn(
        "border rounded-8 p-16 relative w-full copy-small grid has-[>svg]:grid-cols-[auto_1fr] grid-cols-[auto_1fr] has-[>svg]:gap-x-16 gap-y-4 items-center [&>svg]:size-20 [&>svg]:text-current",
        styles,
        className
      )}
    >
      {children}
    </div>
  );
};

export const AlertTitle = ({ children, className = "" }) => (
  <div className={cn("font-semibold col-start-2", className)}>{children}</div>
);

export const AlertDescription = ({
  children,
  className = "",
  copyClass = "copy-small",
}) => <div className={cn("col-start-2", className)}>{children}</div>;
