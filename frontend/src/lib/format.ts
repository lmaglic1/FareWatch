// Display helpers. Prices are decimal strings; we format without float math
// except Intl's own rendering of a 2-decimal value (exact for cents).

export function money(value: string | null | undefined, currency = "EUR"): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return new Intl.NumberFormat("en-GB", { style: "currency", currency, minimumFractionDigits: 2 }).format(n);
}

export function pct(value: string | null | undefined, signed = true): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  return `${signed && n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

/** Local airport time, e.g. "21:10" with its zone label. */
export function localTime(t: string | null | undefined): string {
  return t ? t.slice(0, 5) : "—";
}

export function tzCity(tz: string): string {
  return tz.split("/").pop()?.replace("_", " ") ?? tz;
}

export function dateLong(d: string): string {
  const [y, m, day] = d.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, day)).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** A UTC timestamp shown in the viewer's local time. */
export function timestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timestampUtc(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

export function daysUntil(flightDate: string): number {
  const [y, m, d] = flightDate.split("-").map(Number);
  const today = new Date();
  const t = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((Date.UTC(y, m - 1, d) - t) / 86400000);
}

export const label = (s: string) =>
  ({
    under_seat_only: "Under-seat bag only",
    priority_trolley: "Priority + cabin trolley",
    checked_bag: "Checked bag",
    unknown: "Unknown",
    public: "Public fare",
    member: "Discount Club member",
    basic: "Basic",
    wizz_go: "Wizz GO",
    wizz_plus: "Wizz PLUS",
    yes: "Yes",
    no: "No",
  })[s] ?? s;
