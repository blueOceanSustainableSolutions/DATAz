// Format a date in UTC as YYYY-MM-DD.
export function dateKeyUTC(dateLike) {
  if (!dateLike) return "";
  const d = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (Number.isNaN(d.getTime())) return "";

  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");

  return `${yyyy}-${mm}-${dd}`;
}

export function formatDateToDDMMYYYY(dateString) {
  if (!dateString) return "";

  const date = new Date(dateString);

  const day = date.getUTCDate().toString().padStart(2, "0");
  const month = (date.getUTCMonth() + 1).toString().padStart(2, "0");
  const year = date.getUTCFullYear();

  return `${day}-${month}-${year}`;
}
