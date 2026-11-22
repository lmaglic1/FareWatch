import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ObservationTable, ProfileBlock } from "../components/FlightAnalysis";
import { Card, DemoWatermark, Empty, ErrorBox, Loading, Notice, StatusPill } from "../components/ui";
import { exploreApi, type RouteFlight, type SearchOutcome } from "../lib/api";
import { ago, dateLong, localTime, money, tzCity } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function FlightBlock({ item }: { item: RouteFlight }) {
  const f = item.flight;
  const p = item.analysis.primary;
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-ink-3">{f.airline} · {f.flight_number}</div>
          <div className="mt-0.5 text-lg font-semibold text-ink">
            {localTime(f.scheduled_departure_local)} <span className="text-sm font-normal text-ink-3">{tzCity(f.origin_tz)}</span>
            {" → "}
            {localTime(f.scheduled_arrival_local)} <span className="text-sm font-normal text-ink-3">{tzCity(f.destination_tz)}</span>
          </div>
        </div>
        {p && (
          <div className="flex items-center gap-3">
            <span className="text-2xl font-semibold tabular-nums">{money(p.stats.latest, p.profile.currency)}</span>
            <StatusPill status={p.stats.status} />
          </div>
        )}
      </div>
      {item.analysis.note && <Notice>{item.analysis.note}</Notice>}
      {item.analysis.profiles.map((pr) => <ProfileBlock key={pr.profile_label} p={pr} obs={item.observations} />)}
      <Card title={`All prices recorded (${item.observations.length})`}>
        <ObservationTable obs={item.observations} />
      </Card>
    </section>
  );
}

export default function Route() {
  const { origin = "SJJ", destination = "", date = "" } = useParams();
  const location = useLocation();
  const { data, error, loading, reload } = useAsync(() => exploreApi.route(origin, destination, date), [origin, destination, date]);
  const [searching, setSearching] = useState(false);
  const [outcome, setOutcome] = useState<SearchOutcome | null>(null);
  const [searchErr, setSearchErr] = useState<string | null>(null);
  const autoRan = useRef<string | null>(null);

  async function runSearch() {
    setSearching(true);
    setSearchErr(null);
    try {
      setOutcome(await exploreApi.searchRoute(origin, destination, date));
      reload();
    } catch (e) {
      setSearchErr((e as Error).message);
    } finally {
      setSearching(false);
    }
  }

  // Coming from the search bar or a deal card: search once automatically.
  // (The backend skips the query if this route was checked recently.)
  useEffect(() => {
    const key = `${origin}-${destination}-${date}`;
    const wants = (location.state as { search?: boolean } | null)?.search;
    if (wants && autoRan.current !== key) {
      autoRan.current = key;
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin, destination, date]);

  const o = data?.origin;
  const d = data?.destination;
  const nonstopNone = outcome && outcome.status === "not_found";

  return (
    <>
      <DemoWatermark show={!!data?.demo} />
      <div className="mb-2 text-sm"><Link to="/" className="text-ink-3 hover:text-ink">← All deals</Link></div>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            {o?.city ?? origin} → {d?.city ?? destination}
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            {date && dateLong(date)} · one way · {o?.code ?? origin} → {d?.code ?? destination}
            {d?.name && <span className="text-ink-3"> ({d.name})</span>}
          </p>
          <p className="mt-1 text-xs text-ink-3">
            Last checked: {data?.trip?.last_checked_utc ? ago(data.trip.last_checked_utc) : "never"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={runSearch} disabled={searching}>
            {searching ? "Checking prices…" : "Check latest price"}
          </button>
          {data?.booking_links.map((b) => (
            <a key={b.url} className="btn-ghost" href={b.url} target="_blank" rel="noopener noreferrer" title={b.note}>{b.label} ↗</a>
          ))}
        </div>
      </div>

      {searching && <div className="mb-4"><Loading label="Asking Google Flights for current prices and price history…" /></div>}
      {searchErr && <div className="mb-4"><ErrorBox message={searchErr} /></div>}
      {outcome && !searching && (
        <div className="mb-6"><Notice tone={outcome.status === "success" ? "neutral" : "warn"}>{outcome.message}</Notice></div>
      )}

      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data && (
        data.flights.length === 0 ? (
          <Empty title={nonstopNone ? "No nonstop flights with a price on this date" : "No prices recorded for this route and date yet"}>
            {nonstopNone
              ? "FareWatch tracks nonstop flights only. This route may need a connection, or may not fly on this day. Try another date, or open Google Flights to see connecting options."
              : 'Click "Check latest price" to fetch the current fare and about two months of price history (uses 1 search).'}
          </Empty>
        ) : (
          <div className="space-y-10">
            {data.flights.length > 1 && (
              <p className="text-sm text-ink-2">{data.flights.length} nonstop flights on this date, cheapest first.</p>
            )}
            {data.flights.map((item) => <FlightBlock key={item.flight.id} item={item} />)}
          </div>
        )
      )}

      <div className="mt-8">
        <Notice tone="warn">
          Prices are past observations from Google Flights (via SerpApi) and may have changed. The fare assumes a basic
          ticket with only a free under-seat bag. Check the final price, including bags, on the airline's site. The
          status label is a rule of thumb based on recent history, not a prediction.
        </Notice>
      </div>
    </>
  );
}
