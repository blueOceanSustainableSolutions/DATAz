import { twMerge } from "tailwind-merge";
import clsx from "clsx";

/**
 * Combines class names using
 * clsx and tailwind-merge to handle conflicts.
 *
 * @param  {string[]} classes
 * @returns {string}
 */

export const cn = (...classes) => {
  return twMerge(clsx(...classes));
};
