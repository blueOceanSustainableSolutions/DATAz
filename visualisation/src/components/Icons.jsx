export const DetectionsIcon = ({ type = "", color = "" }) => {
  // Normalize the type to lowercase for easier comparison
  const normalizedType = typeof type === "string" ? type.toLowerCase() : "";

  // Debug log to see what's being passed
  if (type === "dolphins" || type === "dolphin") {
    return (
      <svg
        width="28"
        height="29"
        viewBox="0 0 28 29"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M16.2229 3.57227C10.723 3.57227 6.25051 7.71869 6.16992 12.8875H16.2229V22.4868C21.7833 22.4868 26.2759 18.2457 26.2759 13.039C26.2759 7.83229 21.7833 3.57227 16.2229 3.57227Z"
          fill={color}
        />
        <path
          d="M9.99754 21.0288H16.4443C16.7465 21.0288 16.9681 21.256 16.9681 21.5211V27.6934C16.9681 28.2235 16.1824 28.3939 15.9608 27.9017L13.9865 23.831C13.9261 23.7174 13.8455 23.6227 13.7246 23.5848L9.77593 21.9755C9.25213 21.7672 9.4133 21.0288 9.99754 21.0288Z"
          fill={color}
        />
        <path
          d="M16.0031 4.95437H20.5965C20.7778 4.95437 20.9188 4.82183 20.9188 4.65143V0.31567C20.9188 0.0316682 20.5562 -0.100866 20.3547 0.0884685L15.7815 4.42423C15.5599 4.61356 15.7211 4.95437 16.0031 4.95437Z"
          fill={color}
        />
        <path
          d="M3.31516 12.8682H8.93597C9.11728 12.8682 9.25831 12.6789 9.25831 12.4517V10.1986C9.25831 9.87675 8.9964 9.66848 8.7748 9.81995L3.29501 12.0162C3.07341 12.1109 2.93238 12.376 3.03311 12.6221C3.07341 12.7736 3.17414 12.8682 3.31516 12.8682Z"
          fill={color}
        />
      </svg>
    );
  } else if (type === "whale") {
    return (
      <svg
        width="26"
        height="26"
        viewBox="0 0 26 26"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M25.6001 4.04689V1.14189C25.6001 0.952894 25.3901 0.798894 25.1381 0.805894C22.4921 0.889894 21.2531 1.86989 20.6931 2.88489C20.1331 1.86989 18.8941 0.889894 16.2481 0.805894C15.9961 0.798894 15.7861 0.952894 15.7861 1.14189V4.04689C15.7861 4.04689 15.7581 5.36289 19.0131 5.76889V8.61789C19.0131 8.61789 18.8171 10.2699 17.3611 10.2699C15.9051 10.2699 4.90114 10.2699 3.78814 10.2699C1.81414 10.2699 0.869141 10.6689 0.869141 12.7479C0.869141 14.8269 0.869141 19.9509 0.869141 19.9509C0.869141 19.9509 1.10014 21.7079 3.21414 21.7079C4.48814 21.7079 7.82014 21.7079 10.6761 21.7079L14.1971 25.2289C14.4631 25.4949 14.9181 25.3059 14.9181 24.9279V21.7009C14.9321 21.7009 14.9461 21.7009 14.9601 21.7009C19.3421 21.7009 22.2541 17.7809 22.2541 14.1829C22.2541 10.1299 22.2541 6.79789 22.2541 5.77589C25.6211 5.40489 25.6001 4.04689 25.6001 4.04689Z"
          fill={color}
        />
      </svg>
    );
  } else if (
    type === "HFV" ||
    normalizedType === "hfv" ||
    normalizedType === "vessel-hf" ||
    normalizedType === "vessels-hf" ||
    normalizedType.includes("high") ||
    normalizedType.includes("hf")
  ) {
    return (
      <svg
        width="28"
        height="28"
        viewBox="0 0 164 164"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M127.266 73.6104C129.416 73.6104 130.866 76.9804 129.966 79.9404L128.636 104.33C128.176 105.96 127.076 107 125.926 107H40.8252C39.9793 106.999 38.5471 105.514 38.5332 105.5L8.03223 80C6.03173 77 7.03351 73.6699 10.2158 73.6699H61.9561L127.256 73.6299L127.266 73.6104ZM30 78C27.2392 78 25 80.2354 25 83C25 85.7646 27.2392 88 30 88C32.7608 88 35 85.7646 35 83C35 80.2445 32.7608 78 30 78Z"
          fill={color}
        />
        <path
          d="M118.724 74.37H43.5332C43.5332 74.37 44.5332 71.5 45.0332 70C45.5332 68.5 47.8282 66.87 49.2367 66.87C50.6452 66.87 53.5327 66.87 53.5327 66.87C53.5327 66.87 54.9456 63.1458 56.5327 61C57.5984 59.5592 59.5327 58 59.5327 58C59.5327 58 61.5327 56 64.5327 56C67.5327 56 103.033 56 103.033 56C106.033 56 107.033 56.5 108.104 58.67L112.2 67.0002C112.2 67.0002 116.579 66.5702 118.724 68.0002C121.081 69.5727 122.2 74.37 122.2 74.37H118.724Z"
          fill={color}
        />
        <path
          d="M100 56H123.5C124.328 56 125 56.6716 125 57.5V57.5C125 58.3284 124.328 59 123.5 59H100V56Z"
          fill={color}
        />
        <rect x="131.033" y="70" width="24" height="3" rx="1.5" fill={color} />
        <rect x="131.033" y="84" width="24" height="3" rx="1.5" fill={color} />
        <rect x="131.033" y="98" width="24" height="3" rx="1.5" fill={color} />
        <rect x="120.033" y="63" width="23" height="3" rx="1.5" fill={color} />
        <rect x="145.033" y="63" width="11" height="3" rx="1.5" fill={color} />
        <rect x="132.033" y="77" width="11" height="3" rx="1.5" fill={color} />
        <rect x="145.033" y="77" width="11" height="3" rx="1.5" fill={color} />
        <rect x="132.033" y="91" width="11" height="3" rx="1.5" fill={color} />
        <rect x="145.033" y="91" width="11" height="3" rx="1.5" fill={color} />
      </svg>
    );
  } else {
    return (
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M21.9328 7.02613L23.4893 10.8001C23.5748 11.0686 23.7544 11.2394 23.9597 11.2312H27.4918C27.8595 11.2312 28.1075 11.7843 27.9536 12.2723L25.3366 20.7313C25.2596 20.9998 25.0715 21.1706 24.8748 21.1706H5.73493C5.58955 21.1706 5.45271 21.0811 5.35864 20.9266L0.133239 12.4676C-0.166089 11.9958 0.0733731 11.2394 0.509536 11.2394H3.87911C4.02449 11.2394 4.16133 11.1499 4.2554 10.9954L7.60787 6.83092C7.70194 6.67638 7.83878 6.58691 7.98417 6.58691H21.471C21.6677 6.58691 21.8473 6.75772 21.9328 7.02613ZM14.3553 15.5096C14.3553 16.0082 13.9303 16.4124 13.406 16.4124C12.8817 16.4124 12.4567 16.0082 12.4567 15.5096C12.4567 15.011 12.8817 14.6068 13.406 14.6068C13.9303 14.6068 14.3553 15.011 14.3553 15.5096ZM17.2799 16.4125C17.8042 16.4125 18.2292 16.0083 18.2292 15.5097C18.2292 15.0111 17.8042 14.6068 17.2799 14.6068C16.7557 14.6068 16.3306 15.0111 16.3306 15.5097C16.3306 16.0083 16.7557 16.4125 17.2799 16.4125ZM22.1126 15.5097C22.1126 16.0083 21.6875 16.4125 21.1633 16.4125C20.639 16.4125 20.214 16.0083 20.214 15.5097C20.214 15.0111 20.639 14.6068 21.1633 14.6068C21.6875 14.6068 22.1126 15.0111 22.1126 15.5097Z"
          fill={color}
        />
      </svg>
    );
  }
};

export const CalendarIcon = ({ extraClass }) => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={extraClass}
  >
    <path
      d="M1.5809 5.99971C2.83443 5.99971 4.79077 5.99971 4.79077 5.99971C4.79077 5.99971 4.79077 5.99971 4.79077 5.99971H8.00065C8.00065 5.99971 8.00065 5.99971 8.00065 5.99971C8.00065 5.99971 9.95699 5.99971 11.2105 5.99971C12.4641 5.99971 14.4204 5.99971 14.4204 5.99971M4.05003 2.66634V1.33301M11.9513 2.66634V1.33301M2.33398 13.9996H13.6673C14.2196 13.9996 14.6673 13.5519 14.6673 12.9996V3.93301C14.6673 3.38072 14.2196 2.93301 13.6673 2.93301H2.33398C1.7817 2.93301 1.33398 3.38072 1.33398 3.93301L1.33398 12.9996C1.33398 13.5519 1.7817 13.9996 2.33398 13.9996Z"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const CloseIcon = ({ extraClass }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth="1.5"
    stroke="currentColor"
    className={extraClass}
    width="24"
    height="24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M6 18 18 6M6 6l12 12"
    />
  </svg>
);

export const ChevronDown = ({ extraClass }) => (
  <svg
    width="12"
    height="7"
    viewBox="0 0 12 7"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={extraClass}
  >
    <path
      d="M10.8994 0.949707L5.94967 5.89945L0.999919 0.949707"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const ErrorIcon = ({ extraClass = "" }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 17"
    fill="currentColor"
    strokeWidth="1.5"
    stroke="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    className={extraClass}
  >
    <circle cx="8" cy="8.5" r="7.5" />
    <path
      d="M5 5.5L11 11.5M11 5.5L5 11.5"
      stroke="white"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const PlayIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 20 20"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M2 17.2902V2.70985C2 1.94502 2.82366 1.46331 3.49026 1.83827L16.4505 9.12842C17.1302 9.51073 17.1302 10.4893 16.4505 10.8716L3.49026 18.1617C2.82366 18.5367 2 18.055 2 17.2902Z"
      fill="currentColor"
      stroke="currentColor"
      strokeLinejoin="round"
    />
  </svg>
);

export const PauseIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 20 20"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <rect x="4" y="2" width="2.5" height="16" fill="currentColor" stroke="currentColor" />
    <rect x="13" y="2" width="2.5" height="16" fill="currentColor" stroke="currentColor" />
  </svg>
);

export const RefreshIcon = ({ className = "" }) => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path
      d="M4 4V9H9"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M20 20V15H15"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M21 12C21 13.1819 20.7672 14.3522 20.3149 15.4442C19.8626 16.5361 19.1997 17.5282 18.364 18.364C17.5282 19.1997 16.5361 19.8626 15.4442 20.3149C14.3522 20.7672 13.1819 21 12 21C10.8181 21 9.64778 20.7672 8.55585 20.3149C7.46392 19.8626 6.47177 19.1997 5.63604 18.364C4.80031 17.5282 4.13738 16.5361 3.68508 15.4442C3.23279 14.3522 3 13.1819 3 12C3 9.61305 3.94821 7.32387 5.63604 5.63604C7.32387 3.94821 9.61305 3 12 3C14.3869 3 16.6761 3.94821 18.364 5.63604C20.0518 7.32387 21 9.61305 21 12Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const ResetIcon = ({ size = 14, extraClass = "" }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    width={size}
    height={size}
    className={extraClass}
    aria-hidden
  >
    <path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.36 2.64L3 8" />
    <path d="M3 3v5h5" />
  </svg>
);

export const InfoCircleIcon = ({ extraClass = "" }) => (
  <svg
    width="20"
    height="20"
    xmlns="http://www.w3.org/2000/svg"
    fill="currentColor"
    className={extraClass}
    viewBox="0 0 16 16"
  >
    <path d="M9.585 2.568a.5.5 0 0 1 .226.58L8.677 6.832h1.99a.5.5 0 0 1 .364.843l-5.334 5.667a.5.5 0 0 1-.842-.49L5.99 9.167H4a.5.5 0 0 1-.364-.843l5.333-5.667a.5.5 0 0 1 .616-.09z" />
    <path d="M2 4h4.332l-.94 1H2a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h2.38l-.308 1H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2" />
    <path d="M2 6h2.45L2.908 7.639A1.5 1.5 0 0 0 3.313 10H2zm8.595-2-.308 1H12a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H9.276l-.942 1H12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z" />
    <path d="M12 10h-1.783l1.542-1.639q.146-.156.241-.34zm0-3.354V6h-.646a1.5 1.5 0 0 1 .646.646M16 8a1.5 1.5 0 0 1-1.5 1.5v-3A1.5 1.5 0 0 1 16 8" />
  </svg>
);

export const InfoOutlinedIcon = ({ extraClass }) => (
  <svg
    className={extraClass}
    width="24"
    height="24"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth="1.5"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
    />
  </svg>
);

export const SpinnerIcon = ({ extraClass }) => (
  <svg
    className={extraClass}
    width="24"
    height="24"
    fill="none"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
  >
    <circle
      className="opacity-25"
      cx="12"
      cy="12"
      r="10"
      stroke="currentColor"
      strokeWidth="4"
    />
    <path
      className="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
    />
  </svg>
);

export const NavigationIcon = ({ extraClass, style }) => (
  <svg
    className={extraClass}
    width="20"
    height="20"
    fill="currentColor"
    viewBox="0 0 24 24"
    style={style}
  >
    <path d="M12 2 4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"></path>
  </svg>
);

export const FitToFleetIcon = ({ size = 20, extraClass = "" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width={size} height={size} className={extraClass}>
    <path d="M3 7V3h4M21 7V3h-4M3 17v4h4M21 17v4h-4" />
  </svg>
);

export const ControlPanelIcon = ({ size = 20, extraClass = "" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width={size} height={size} className={extraClass}>
    <line x1="4"  y1="6"  x2="14" y2="6" />
    <circle cx="18" cy="6"  r="2" />
    <line x1="10" y1="12" x2="20" y2="12" />
    <circle cx="6"  cy="12" r="2" />
    <line x1="4"  y1="18" x2="14" y2="18" />
    <circle cx="18" cy="18" r="2" />
  </svg>
);
