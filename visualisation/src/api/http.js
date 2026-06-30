import { API_BASE, API_KEY } from "@/config";

// Backend API base, e.g. `https://…/api`.
export const API = API_BASE;

function request(url) {
  return fetch(url, {
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    cache: "no-store",
  });
}

/**
 * Authenticated GET returning JSON.
 *
 * - Attaches the configured API key as `X-API-Key`.
 * - Preserves the 422 contract: a row-guard rejection is surfaced as an error
 *   with `code === "too_many_rows"` so charts show a non-blocking inline prompt.
 */
export async function getJson(url) {
  const res = await request(url);

  if (res.status === 422) {
    const body = await res.json().catch(() => ({}));
    const err = new Error("too_many_rows");
    err.status = 422;
    err.code = "too_many_rows";
    err.suggestion = body.suggestion;
    throw err;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.message || `request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }

  return res.json();
}

export function iso(d) {
  return typeof d === "string" ? d : d.toISOString();
}
