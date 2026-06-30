const ChartCard = ({ children, extraClass = "" }) => {
  return (
    <div
      className={`min-h-240 768:min-h-320 1440:min-h-325 1680:min-h-400 h-full min-w-0 overflow-hidden bg-surface rounded-8 p-16 768:p-24 drop-shadow-default ${extraClass}`}
    >
      {children}
    </div>
  );
};

export default ChartCard;
