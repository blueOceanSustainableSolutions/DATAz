import { SPL_OFFSETS } from "@/constants/scoutConfig";

/**
 * Chart utilities — per-hydrotwin SPL calibration offsets for the site charts.
 */

/**
 * Check if scout is HT-S-003, HT-S-004, or HT-S-006+ series
 * These scouts use the same configuration: 28 frequency bands, 0 SPL offset, p25/p50/p75 percentiles
 * @param {string} scoutId - The ID of the scout
 * @returns {boolean} True if scout is HT-S-003, HT-S-004, or HT-S-006+
 */
export function isHts6PlusOrHts003(scoutId) {
  if (!scoutId) return false;
  const idLower = String(scoutId).toLowerCase();
  // HT-S-003 and HT-S-004 use same config as HT-S-006+
  if (idLower === "ht-s-003" || idLower === "ht-s-004") return true;
  const match = idLower.match(/^ht-s-(\d+)$/);
  return match && parseInt(match[1]) >= 6;
}

export function getOffsetSPL(scoutId) {
  if (!scoutId) return SPL_OFFSETS.default;

  const lowerId = scoutId.toLowerCase();

  // Check if it's an HT-S scout with ID 6 or above
  const htSMatch = lowerId.match(/^ht-s-(\d+)$/);
  if (htSMatch && parseInt(htSMatch[1]) >= 6) {
    return SPL_OFFSETS["ht-s-6-plus"];
  }

  // Return specific offset if defined, otherwise default
  return SPL_OFFSETS[lowerId] || SPL_OFFSETS.default;
}

/**
 * Per-hydrotwin SPL calibration offset for the Site (multi-deployment) charts.
 * Mirrors the deployment's per-device offset but keyed only on the htId, since
 * the site measurement readings carry no deploymentId — so the legacy Borealis
 * deployment offset (keyed by deployment id 24/28) can't be matched here and
 * falls back to the default. HT-S-003/004/006+ are already calibrated (0).
 */
export function siteSplOffset(htId) {
  return isHts6PlusOrHts003(htId) ? 0 : getOffsetSPL(htId);
}
