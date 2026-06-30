import { useState, useRef, useEffect } from "react";
import { ChevronDown, ErrorIcon } from "./Icons";

/**
 * CustomSelect — themed listbox/dropdown.
 *
 * `openUp` flips the menu above the trigger (for controls anchored to the bottom
 * of the viewport, e.g. the overlay playback bar). `searchable` adds a filter
 * input; `compact` shrinks padding/type for dense toolbars.
 */
const CustomSelect = ({
  label,
  placeholder,
  options,
  selectedOption,
  setSelectedOption,
  optionSuffix,
  hasOptionsTitle = true,
  error = false,
  extraClass = "",
  compact = false,
  searchable = false,
  openUp = false,
}) => {
  const selectRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const toggleDropdown = () => setIsOpen(!isOpen);

  const handleOptionSelect = (option) => {
    setSelectedOption(option);
    setIsOpen(false);
    setQuery("");
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (selectRef.current && !selectRef.current.contains(event.target)) {
        setIsOpen(false);
        setQuery("");
      }
    };
    window.addEventListener("click", handleClickOutside);
    return () => {
      window.removeEventListener("click", handleClickOutside);
    };
  }, []);

  const visibleOptions =
    searchable && query.trim()
      ? options.filter((o) =>
          String(o).toLowerCase().includes(query.trim().toLowerCase()),
        )
      : options;

  return (
    <div ref={selectRef}>
      {label && (
        <label id="listbox-label" className="block mb-8 copy-small text-textPrimary">
          {label}
        </label>
      )}
      <div className="relative">
        <button
          type="button"
          className={`w-full flex justify-between gap-x-8 items-center cursor-default ${
            compact ? "px-8 py-6" : "px-16 py-13"
          } rounded-4 bg-surface border text-left ${
            error ? "border-error" : "border-grey300"
          } ${extraClass}`}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-labelledby="listbox-label"
          onClick={toggleDropdown}
        >
          {selectedOption ? (
            <span className={`${compact ? "copy-small" : "copy-body"} whitespace-nowrap`}>
              {selectedOption} {optionSuffix && optionSuffix}
            </span>
          ) : (
            <span
              className={`${compact ? "copy-small" : "copy-body"} text-grey500 whitespace-nowrap`}
            >
              {placeholder}
            </span>
          )}
          <div className={isOpen ? "rotate-180" : ""}>
            <ChevronDown />
          </div>
        </button>
        {error && (
          <div className="flex items-center gap-x-8 mt-8">
            <ErrorIcon />
            <span className="block copy-extrasmall text-red-500">{error}</span>
          </div>
        )}

        {isOpen && (
          <div
            className={`absolute z-10 w-full min-w-max rounded-4 bg-surface drop-shadow-default overflow-hidden ${
              openUp ? "bottom-full mb-2" : "mt-2"
            }`}
          >
            {searchable && (
              <div className="p-8 border-b border-grey200">
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search..."
                  className="w-full px-12 py-8 copy-small rounded-4 bg-surface border border-grey300 text-textPrimary focus:outline-none focus:border-primary"
                />
              </div>
            )}
            <ul
              className="p-8 h-auto max-h-208 overflow-auto"
              tabIndex="-1"
              role="listbox"
              aria-labelledby="listbox-label"
            >
              {hasOptionsTitle && !searchable && (
                <li className="p-12 rounded-4">
                  <span className="copy-body text-grey400">{placeholder}</span>
                </li>
              )}
              {visibleOptions.length === 0 && (
                <li className="p-12 rounded-4">
                  <span className="copy-small text-grey400">No matches</span>
                </li>
              )}
              {visibleOptions.map((option, index) => (
                <li
                  key={index}
                  className={`relative cursor-default select-none p-12 rounded-4 media-hover:hover:bg-grey100 duration-300 ${
                    option === selectedOption ? "bg-grey300" : ""
                  }`}
                  role="option"
                  aria-selected={option === selectedOption}
                  onClick={() => handleOptionSelect(option)}
                >
                  <span className="block whitespace-nowrap copy-body">
                    {option} {optionSuffix && optionSuffix}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomSelect;
