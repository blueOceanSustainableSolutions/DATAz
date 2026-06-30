
const sizeClasses = {
  large: "copy-body py-15 px-16 rounded-8",
  medium: "copy-body py-9 px-11 rounded-8",
  small: "copy-small py-7 px-8 rounded-4",
  xsmall: "copy-extrasmall py-6 px-10 rounded-8",
};

export const PrimaryButton = ({
  type = "button",
  children,
  size = "large",
  onClick,
  isFullWidth = false,
  extraClass = "",
  disabled = false,
  restProps,
}) => (
  <button
    type={type}
    onClick={onClick}
    className={`flex gap-x-8 h-fit justify-center whitespace-nowrap bg-primary media-hover:hover:bg-primaryHover disabled:opacity-50 disabled:pointer-events-none transition text-white ${
      sizeClasses[size]
    } ${isFullWidth ? "w-full" : "w-fit"} ${extraClass}`}
    disabled={disabled}
    {...restProps}
  >
    {children}
  </button>
);

export const GhostPrimaryButton = ({
  type = "button",
  children,
  onClick,
  extraClass = "",
  disabled = false,
}) => {
  return (
    <button
      type={type}
      onClick={onClick}
      className={`flex gap-x-8 h-fit justify-center copy-small whitespace-nowrap text-primary generic-hover disabled:opacity-50 disabled:pointer-events-none transition ${extraClass}`}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

export const OutlineButton = ({
  children,
  size = "large",
  type = "button",
  onClick,
  isFullWidth = false,
  extraClass = "",
}) => (
  <button
    type={type}
    onClick={onClick}
    className={`flex items-center gap-x-8 h-fit whitespace-nowrap justify-center bg-none border border-grey400 media-hover:hover:bg-grey300 transition ${
      sizeClasses[size]
    } ${isFullWidth ? "w-full" : "w-fit"} ${extraClass}`}
  >
    {children}
  </button>
);

/**
 * Full-width left-aligned button for dropdown list rows.
 * No border or background — relies solely on hover state.
 */
export const ListItemButton = ({
  type = "button",
  children,
  onClick,
  extraClass = "",
}) => (
  <button
    type={type}
    onClick={onClick}
    className={`flex w-full items-center gap-8 px-12 py-8 text-left transition media-hover:hover:bg-grey100 ${extraClass}`}
  >
    {children}
  </button>
);
