import { useMemo } from "react";
import { TabGroup, TabList, TabPanels, TabPanel, Tab } from "@headlessui/react";
import { cn } from "@/lib/classnames";

/**
 * @typedef {Object} Tab
 * @property {string} key - Unique key for the tab
 * @property {string} name - Display name of the tab
 * @property {JSX.Element} panel - Content to render when the tab is active
 * @property {boolean} [disabled] - Whether the tab is disabled
 * @property {boolean} [hidden] - Whether the tab is hidden
 */

/**
 *
 * @param {Objects} props
 * @param {Tab[]} props.tabs - Array of tab objects
 * @param {JSX.Element} [props.rightSlot] - Optional element to render on the right side of the tab list
 * @param {(tab: Tab) => boolean} [props.filter] - Optional filter function to determine which tabs to display
 * @returns
 */

export const TabRenderer = ({
  tabs = [],
  rightSlot = null,
  filter = (t) => !t.hidden,
  defaultIndex = 0,
  selectedIndex,
  onChange,
  flushHeader = false,
}) => {
  const visibleTabs = useMemo(
    () => (tabs ?? []).filter(filter),
    [tabs, filter],
  );

  const isControlled = selectedIndex !== undefined;

  return (
    <TabGroup
      {...(isControlled ? { selectedIndex, onChange } : { defaultIndex })}
    >
      <div
        className={cn(
          "flex min-w-0 flex-col justify-between items-stretch gap-8 1024:flex-row 1024:gap-16",
          flushHeader
            ? "py-8 768:py-24 1024:items-center"
            : "p-8 768:p-24 1024:items-start",
        )}
      >
        <TabList className="flex max-w-full gap-4 768:gap-8 overflow-x-auto p-6 768:p-8 rounded-8 bg-grey300">
          {visibleTabs.map((t) => (
            <Tab
              key={t.key}
              disabled={!!t.disabled}
              title={t.disabled ? t.disabledReason : undefined}
              onClick={t.onClick ? t.onClick : undefined}
              className={cn(
                "copy-body shrink-0 whitespace-nowrap rounded-8 px-10 py-6 768:px-16 768:py-8 border-none outline-none data-[selected]:bg-primary data-[selected]:text-white",
                !t.disabled && "hover:bg-surface/40",
                t.disabled &&
                  "opacity-50 cursor-not-allowed pointer-events-none",
              )}
            >
              {t.name}
            </Tab>
          ))}
        </TabList>

        {rightSlot ? <div className="w-full 1024:w-fit">{rightSlot}</div> : null}
      </div>

      <TabPanels>
        {visibleTabs.map((t) => (
          <TabPanel key={t.key} unmount={!t.keepMounted}>
            {t.panel}
          </TabPanel>
        ))}
      </TabPanels>
    </TabGroup>
  );
};
