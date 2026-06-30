/**
 * This function calculates the used SD card space in GB based on the deployment date.
 * Assumptions:
 * - The SD card has a total capacity of 1TB (1024GB).
 * - The average daily data usage is approximately 3.87GB.
 *
 * @param {Date} deploymentDate
 * @returns {number | null} - Used SD card space in GB or null if deploymentDate is invalid
 */

export function calcUsedSDCardGB(deploymentDate) {
  if (!deploymentDate || isNaN(new Date(deploymentDate).getTime())) {
    return null;
  }

  const totalSDCardGB = 1024;
  const dailyDataUsageGB = 3.87;

  const currentDate = new Date();
  const deployDate = new Date(deploymentDate);
  const diffTime = Math.abs(currentDate - deployDate);
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  const usedSDCardGB = diffDays * dailyDataUsageGB;

  return usedSDCardGB > totalSDCardGB
    ? totalSDCardGB
    : Math.round(usedSDCardGB);
}
