/**
 * Configuration for different scout types and their behaviors
 */

import { isHts6PlusOrHts003 } from "@/lib/charts";

const HTS_SD_CAPACITY_GB = 1000;
const HTS_SD_CAPACITY_SMALL_GB = 256;
const SMALL_SD_CARD_SCOUTS = ["ht-s-013", "ht-s-004", "ht-s-023"];

/**
 * Get the SD card capacity for a specific scout
 * @param {string} scoutId - The ID of the scout
 * @returns {number} SD card capacity in GB (256 for specific scouts, 1000 for others)
 */
export const getSDCardCapacityGB = (scoutId) => {
  if (!scoutId) return HTS_SD_CAPACITY_GB;
  const scoutIdLower = scoutId.toLowerCase();
  return SMALL_SD_CARD_SCOUTS.includes(scoutIdLower) ? HTS_SD_CAPACITY_SMALL_GB : HTS_SD_CAPACITY_GB;
};

// Mapping of detection types to their display names for the legend
export const DETECTION_DISPLAY_NAMES = {
  dolphin: "Dolphins",
  dolphins: "Dolphins",
  whale: "Whales",
  whales: "Whales",
  vessel: "Vessel",
  vessels: "Vessels",

  "vessels-hf": "High-Freq Vessels",
  "vessels-mf": "Mid-Freq Vessels",
  "vessels-lf": "Low-Freq Vessels",

  lfv: "Low-Freq Vessels",
  mfv: "Med-Freq Vessels",
  hfv: "High-Freq Vessels",

  repmus_auv62at: "AUV62",
  common: "Sonarfish",
  jm1_gavia_dk: "GAVIA",
  recall_signature: "RECALL",
  repmus_sema_rtsys: "SEMA",
};

const ALL_HT_IDs = [
  "scout-s-002",
  "scout-s-003",
  "scout-s-005",
  "scout-c-002",
  "ht-v-001",
  "ht-s-000",
];

// SPL offset values for different scout types
export const SPL_OFFSETS = {
  // No offset for HT-S 6+ series, HT-S-003, and HT-S-004
  "ht-s-6-plus": 0,
  "ht-s-003": 0,
  "ht-s-004": 0,
  // Default offset for other scouts
  default: 149.82,
};

/**
 * Determines if a scout should use standard percentiles (p25, p50, p75) instead of p99m
 * @param {string} scoutId - The ID of the scout
 * @returns {boolean} True if the scout should use standard percentiles
 */
export const shouldUseStandardPercentiles = (scoutId) => {
  if (!scoutId) return false;

  const scoutIdLower = scoutId.toLowerCase();

  return (
    scoutIdLower.startsWith("borealis") ||
    scoutIdLower.startsWith("ht-v-") ||
    ALL_HT_IDs.includes(scoutIdLower) ||
    isHts6PlusOrHts003(scoutIdLower) ||
    scoutIdLower.startsWith("ht-c-") ||
    scoutIdLower === "ht-s-003" ||
    scoutIdLower === "ht-s-006" ||
    (scoutIdLower.startsWith("ht-s-") &&
      parseInt(scoutIdLower.split("-")[2]) >= 6)
  );
};
