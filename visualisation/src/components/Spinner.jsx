const Spinner = ({
  isLoading,
  size = 48,
  strokeWidth = 4,
  extraClass = "",
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference * 0.5; // 50% visible, 50% hidden

  return (
    isLoading && (
      <div className={`spinner-wrapper ${extraClass}`}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="animate-spin"
        >
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke=""
            className="stroke-black opacity-10"
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Animated circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            className="stroke-chartBase"
            style={{
              transformOrigin: "50% 50%",
            }}
          />
        </svg>
      </div>
    )
  );
};

export default Spinner;
