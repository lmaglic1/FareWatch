import { useState } from "react";
import { Link } from "react-router-dom";
import { ManualEntryForm } from "../components/ManualEntryForm";
import { Card, DemoWatermark, Empty, ErrorBox, Loading, MemberBadge, Notice, PageHeader, SourceBadge, Stat, StatusPill } from "../components/ui";
import { api, type DashboardLeg } from "../lib/api";
import { ago, dateLong, daysUntil, label, localTime, money, pct, timestamp, timestampUtc, tzCity } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function LegCard({ leg }: { leg: DashboardLeg }) {
  const f = leg.flight;
  const p = leg.analysis.primary;
  const s = p?.stats;
  const cur = p?.profile.currency ?? "EUR";
  const latest = leg.latest_observation;
  const best = leg.best_observation;
  const days = s?.days_to_departure ?? daysUntil(f.flight_date);

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-hair px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-ink-3">
              {f.direction === "outbound" ? "Outbound" : "Return"} · {f.airline}
            </div>
            <div className="mt-1 flex items-baseline gap-3">
              <span className="text-2xl font-semibold tracking-tight text-ink">{f.origin} → {f.destination}</span>
              <span className="text-sm font-medium text-ink-2">{f.flight_number}</span>
            </div>
            <div className="mt-1 text-sm text-ink-2">
              {dateLong(f.flight_date)} · {localTime(f.scheduled_departure_local)}{" "}
              <span className="text-ink-3">{tzCity(f.origin_tz)}</span> → {localTime(f.scheduled_arrival_local)}{" "}
              <span className="text-ink-3">{tzCity(f.destination_tz)}</span>
            </div>
            <div className="mt-1 text-xs text-ink-3">
              Schedule: {f.schedule_status === "preliminary" ? "preliminary (not verified as live availability)" : f.schedule_status.replace(/_/g, " ")}
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-semibold tabular-nums text-ink">{days ?? "—"}</div>
            <div className="text-xs text-ink-3">days to departure</div>
          </div>
        </div>
      </div>

      <div className="space-y-5 px-5 py-5">
        {!p ? (
          <Empty title="No comparable quotes yet">
            {leg.analysis.total_quotes
              ? leg.analysis.note
              : "Add a fare you saw below, import a CSV, or connect SerpApi in Settings."}
          </Empty>
        ) : (
          <>
            <div>
              <StatusPill status={s!.status} />
              <p className="mt-2 text-sm text-ink-2">{s!.status_reason}</p>
              <p className="mt-1 text-xs text-ink-3">{s!.heuristic_note}</p>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3">
              <Stat
                label="Last observed"
                value={money(latest?.price_total, cur)}
                badge={latest && <SourceBadge source={latest.source} assumed={latest.profile_assumed} />}
                hint={latest && <span title={timestampUtc(latest.captured_at_utc)}>{timestamp(latest.captured_at_utc)}</span>}
              />
              <Stat
                label="Best recorded"
                value={money(best?.price_total, cur)}
                badge={best && <SourceBadge source={best.source} assumed={best.profile_assumed} />}
                hint={best && timestamp(best.captured_at_utc)}
              />
              <Stat
                label="Median"
                value={money(s!.median, cur)}
                hint={s!.latest_vs_median_pct ? `latest ${pct(s!.latest_vs_median_pct)} vs earlier median` : `${s!.count} quote(s)`}
              />
              <Stat label="7-day median" value={money(s!.median_7d, cur)} hint={s!.median_7d_note ?? `${s!.median_7d_count} quotes`} />
              <Stat label="Change vs previous" value={pct(s!.pct_change_vs_previous)} hint={s!.drop_detected ? "Significant drop" : undefined} />
              <Stat label="Quotes recorded" value={s!.count} hint={`range ${money(s!.min, cur)} – ${money(s!.max, cur)}`} />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
              <span>Profile: {p.profile_label}</span>
              {p.is_member_fare && <MemberBadge />}
              {latest?.profile_assumed && <span>* baggage/fare assumed from provider</span>}
            </div>
          </>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-hair pt-4">
          <div className="text-xs text-ink-3">
            Data freshness: {leg.analysis.last_valid_quote_at ? ago(leg.analysis.last_valid_quote_at) : "no data"}
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="btn-ghost" to={`/flights/${f.id}`}>Details & chart</Link>
            {leg.booking_links.map((b) => (
              <a key={b.url} className="btn-ghost" href={b.url} target="_blank" rel="noopener noreferrer" title={b.note}>
                {b.label} ↗
              </a>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Dashboard() {
  const { data, error, loading, reload } = useAsync(() => api.dashboard());
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      const r = await api.runCollector(false);
      setRefreshMsg(
        r.ran
          ? r.results.map((x) => `${x.route}: ${x.status.replace(/_/g, " ")}${x.message ? ` (${x.message})` : ""}`).join(" · ")
          : r.reason ?? "Not run",
      );
      reload();
    } catch (e) {
      setRefreshMsg((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  }

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;
  const flights = data.legs.map((l) => l.flight);
  const c = data.combined_legs;

  return (
    <>
      <DemoWatermark show={data.demo} />
      <PageHeader
        title="New Year in Rome"
        subtitle={<>Sarajevo ⇄ Rome Fiumicino · 31 Dec 2026 – 5 Jan 2027 · {data.preferences.passengers} adult, economy, direct, {data.preferences.display_currency}</>}
        actions={
          <button className="btn-ghost" onClick={refresh} disabled={refreshing || !data.provider.serpapi_configured}
            title={data.provider.serpapi_configured ? "Query SerpApi now: current price + Google's ~60-day price history for both legs (2 searches, respects daily cap)" : "Add SERPAPI_API_KEY to enable"}>
            {refreshing ? "Checking…" : "Refresh prices now"}
          </button>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-ink-2">
        <span className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${data.provider.serpapi_configured ? "bg-good" : "bg-ink-3"}`} />
          SerpApi {data.provider.serpapi_configured ? "connected" : "not connected"}
        </span>
        <span>Last successful fetch: {data.provider.last_successful_fetch_utc ? timestamp(data.provider.last_successful_fetch_utc) : "never"}</span>
        <span>Scheduled checks: {data.provider.collector_enabled ? `on (${data.preferences.collector_times})` : "off"}</span>
      </div>
      {refreshMsg && <div className="mb-6"><Notice>{refreshMsg}</Notice></div>}

      <div className="grid gap-6 xl:grid-cols-2">
        {data.legs.map((leg) => <LegCard key={leg.flight.id} leg={leg} />)}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card title="Trip total (both legs)" className="lg:col-span-2">
          {c.available ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Latest legs combined" value={money(c.latest_total, c.currency)} />
                <Stat label="Best legs combined" value={money(c.best_total, c.currency)} />
              </div>
              <p className="text-xs text-ink-3">{c.note}</p>
            </div>
          ) : (
            <div className="space-y-2 text-sm text-ink-2">
              <p>Not combined. Legs are only added when their fare assumptions match:</p>
              <ul className="list-disc space-y-0.5 pl-5 text-xs text-ink-3">
                {c.reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
          {data.latest_round_trip_quote && (
            <div className="mt-4 border-t border-hair pt-4">
              <Stat
                label="Latest quoted round trip (separate quote)"
                value={money(data.latest_round_trip_quote.price_total, data.latest_round_trip_quote.currency)}
                badge={<SourceBadge source={data.latest_round_trip_quote.source} />}
                hint={`${timestamp(data.latest_round_trip_quote.captured_at_utc)} · ${label(data.latest_round_trip_quote.baggage_profile)}`}
              />
            </div>
          )}
          <div className="mt-5"><Notice tone="warn">{data.disclaimer}</Notice></div>
        </Card>

        <Card title="Record a fare you saw" className="lg:col-span-3">
          <ManualEntryForm flights={flights} displayCurrency={data.preferences.display_currency} onSaved={reload} />
        </Card>
      </div>
    </>
  );
}
