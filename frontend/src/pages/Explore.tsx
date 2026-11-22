import { useState } from "react";
import { Link } from "react-router-dom";
import { SearchBar } from "../components/SearchBar";
import { Empty, ErrorBox, Loading, Notice } from "../components/ui";
import { exploreApi, type ExploreDestination, type ExploreView, type TripType } from "../lib/api";
import { ago, money } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const DURATIONS = [
  { v: 1, label: "Weekend" },
  { v: 2, label: "1 week" },
  { v: 3, label: "2 weeks" },
];

/** Google Travel Explore only offers the next 6 months. */
function nextMonths(): { v: number; label: string }[] {
  const out = [{ v: 0, label: "Any time (next 6 months)" }];
  const d = new Date();
  for (let i = 0; i < 6; i++) {
    const m = new Date(d.getFullYear(), d.getMonth() + i, 1);
    out.push({ v: m.getMonth() + 1, label: m.toLocaleDateString("en-GB", { month: "long", year: "numeric" }) });
  }
  return out;
}

function shortDate(d: string | null) {
  if (!d) return null;
  const [y, m, day] = d.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, day)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
}

function hm(min: number | null) {
  if (!min) return null;
  return `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}m`;
}

function DealCard({ d, rank, origin, tripType }: { d: ExploreDestination; rank: number; origin: string; tripType: TripType }) {
  const to = d.start_date ? `/route/${origin}/${d.airport_code}/${d.start_date}` : null;
  const stops = d.stops === 0 ? "Nonstop" : d.stops === 1 ? "1 stop" : d.stops ? `${d.stops} stops` : null;
  const body = (
    <>
      <div className="relative h-36 overflow-hidden bg-accent-soft">
        {d.thumbnail ? (
          <img src={d.thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
        ) : (
          <div className="flex h-full items-center justify-center text-3xl font-semibold text-accent-ink">{d.airport_code}</div>
        )}
        {rank < 3 && (
          <span className="absolute left-3 top-3 rounded-full bg-raised px-2.5 py-1 text-[11px] font-semibold text-ink shadow-card">
            {rank === 0 ? "Cheapest" : `#${rank + 1} cheapest`}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-base font-semibold text-ink">{d.name}</div>
            <div className="truncate text-xs text-ink-3">{[d.country, d.airport_code].filter(Boolean).join(" · ")}</div>
          </div>
          <div className="text-right">
            <div className="text-xl font-semibold tabular-nums text-ink">{money(d.price, d.currency)}</div>
            <div className="text-[11px] text-ink-3">{tripType === "round_trip" ? "round trip" : "one way"}</div>
          </div>
        </div>
        <div className="text-sm text-ink-2">
          {shortDate(d.start_date) ?? "Date not given"}
          {d.end_date && <> → {shortDate(d.end_date)}</>}
        </div>
        <div className="mt-auto flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-3">
          {d.airline && <span>{d.airline}</span>}
          {stops && <span className={d.stops === 0 ? "text-good" : ""}>{stops}</span>}
          {hm(d.duration_minutes) && <span>{hm(d.duration_minutes)}</span>}
        </div>
      </div>
    </>
  );
  const cls = "group flex flex-col overflow-hidden rounded-xl bg-surface shadow-card transition hover:-translate-y-0.5 hover:ring-1 hover:ring-accent";
  return to ? (
    <Link to={to} state={{ search: true }} className={cls} title={`See ${d.name} prices on ${d.start_date}`}>{body}</Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export default function Explore() {
  const [tripType, setTripType] = useState<TripType>("one_way");
  const [month, setMonth] = useState(0);
  const [duration, setDuration] = useState(2);
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [override, setOverride] = useState<ExploreView | null>(null);
  const { data, error, loading, reload } = useAsync(() => {
    setOverride(null);
    return exploreApi.explore(tripType, month, duration);
  }, [tripType, month, duration]);
  const view = override ?? data;

  async function refresh() {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      const r = await exploreApi.refresh(tripType, month, duration);
      setOverride(r);
      if (r.status !== "success") setRefreshMsg(r.message ?? r.status ?? null);
    } catch (e) {
      setRefreshMsg((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  }

  const origin = view?.origin ?? "SJJ";
  const months = nextMonths();

  return (
    <>
      <section className="mb-8 pt-2 sm:pt-6">
        <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Cheap flights from Sarajevo</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-2 sm:text-base">
          The lowest fares Google Flights currently shows from Sarajevo, sorted by price. Pick a destination to see its
          price history and whether today's fare is low or high.
        </p>
        <div className="mt-6"><SearchBar origin={origin} /></div>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-lg p-1 ring-1 ring-hair" role="group" aria-label="Trip type">
            {(["one_way", "round_trip"] as TripType[]).map((t) => (
              <button key={t} onClick={() => setTripType(t)} aria-pressed={tripType === t}
                className={`rounded-md px-3 py-1.5 text-sm ${tripType === t ? "bg-raised font-medium text-ink shadow-card" : "text-ink-2"}`}>
                {t === "one_way" ? "One way" : "Round trip"}
              </button>
            ))}
          </div>
          <select className="input w-auto" value={month} onChange={(e) => setMonth(Number(e.target.value))} aria-label="Month">
            {months.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
          </select>
          {tripType === "round_trip" && (
            <select className="input w-auto" value={duration} onChange={(e) => setDuration(Number(e.target.value))} aria-label="Trip length">
              {DURATIONS.map((d) => <option key={d.v} value={d.v}>{d.label}</option>)}
            </select>
          )}
          <div className="ml-auto flex items-center gap-3">
            {view?.snapshot && (
              <span className="text-xs text-ink-3">Updated {ago(view.snapshot.fetched_at_utc)}</span>
            )}
            <button className="btn-ghost" onClick={refresh} disabled={refreshing || (view ? !view.can_refresh : false)}
              title={view && !view.can_refresh && view.next_refresh_utc ? `Next refresh possible ${new Date(view.next_refresh_utc).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : "Uses 1 search"}>
              {refreshing ? "Loading deals…" : view?.snapshot ? "Refresh deals" : "Load deals"}
            </button>
          </div>
        </div>

        {refreshMsg && <div className="mb-4"><Notice tone="warn">{refreshMsg}</Notice></div>}

        {loading && !view ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : !view?.destinations.length ? (
          <Empty title="No deals loaded for this view yet">
            Click "Load deals" to fetch the cheapest destinations from Sarajevo (uses 1 search of your monthly SerpApi
            allowance). Results are saved and can be refreshed every 6 hours.
          </Empty>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {view.destinations.map((d, i) => (
              <DealCard key={`${d.airport_code}-${d.start_date}`} d={d} rank={i} origin={origin} tripType={tripType} />
            ))}
          </div>
        )}

        <p className="mt-6 max-w-3xl text-xs leading-relaxed text-ink-3">
          Prices come from Google Flights (via SerpApi), include taxes for {view?.snapshot?.passengers ?? 1} adult, and
          were correct when fetched. They can change at any time, and baggage is usually extra. No one can know in advance
          when a fare will be cheapest. The dates shown are the cheapest Google found, and each destination page shows
          how the price has moved recently. FareWatch never books anything. Always confirm on the airline's site.
        </p>
      </section>
    </>
  );
}
