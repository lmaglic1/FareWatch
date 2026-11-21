import { Link, useNavigate, useParams } from "react-router-dom";
import { PriceChart } from "../components/PriceChart";
import { Card, DemoWatermark, Empty, ErrorBox, Loading, MemberBadge, Notice, PageHeader, SourceBadge, Stat, StatusPill } from "../components/ui";
import { api, type FlightDetail, type Observation, type ProfileAnalysis } from "../lib/api";
import { dateLong, label, localTime, money, pct, timestamp, timestampUtc, tzCity } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function sameProfile(o: Observation, p: ProfileAnalysis["profile"]) {
  return o.currency === p.currency && o.passengers === p.passengers && o.fare_product === p.fare_product &&
    o.baggage_profile === p.baggage_profile && o.taxes_fees_included === p.taxes_fees_included &&
    o.discount_club === p.discount_club;
}

function ProfileBlock({ p, obs }: { p: ProfileAnalysis; obs: Observation[] }) {
  const s = p.stats;
  const cur = p.profile.currency;
  const rows = obs.filter((o) => sameProfile(o, p.profile));
  return (
    <Card
      title={
        <span className="flex flex-wrap items-center gap-2">
          {p.matches_preferences ? "Your comparison profile" : "Other fare profile (not mixed)"}
          {p.is_member_fare && <MemberBadge />}
        </span>
      }
      action={<StatusPill status={s.status} />}
    >
      <p className="mb-1 text-xs text-ink-3">{p.profile_label}</p>
      <p className="mb-4 text-sm text-ink-2">{s.status_reason}</p>
      {rows.length >= 2 ? (
        <PriceChart observations={rows} median={s.median} />
      ) : (
        <Empty title="Not enough points for a chart">At least two quotes in this profile are needed.</Empty>
      )}
      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">
        <Stat label="Min" value={money(s.min, cur)} />
        <Stat label="Max" value={money(s.max, cur)} />
        <Stat label="Median" value={money(s.median, cur)} />
        <Stat label="Average" value={money(s.mean, cur)} />
        <Stat label="7-day median" value={money(s.median_7d, cur)} hint={s.median_7d_note ?? undefined} />
        <Stat label="vs previous" value={pct(s.pct_change_vs_previous)} hint={s.drop_detected ? "drop detected" : undefined} />
        <Stat label="Rank of latest" value={s.latest_rank ? `${s.latest_rank} of ${s.count}` : "—"} hint="1 = cheapest recorded" />
        <Stat label="Volatility (SD)" value={money(s.volatility_stdev, cur)} hint={s.volatility_cv_pct ? `CV ${Number(s.volatility_cv_pct).toFixed(1)}%` : "needs ≥ 3 quotes"} />
      </div>
    </Card>
  );
}

function ObservationTable({ obs }: { obs: Observation[] }) {
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="min-w-full">
        <thead className="border-b border-hair">
          <tr>
            <th className="th">Captured</th><th className="th text-right">Price</th><th className="th">Source</th>
            <th className="th">Baggage</th><th className="th">Fare</th><th className="th">Club</th><th className="th text-right">Lead (d)</th>
            <th className="th">Link</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hair">
          {[...obs].reverse().map((o) => (
            <tr key={o.id}>
              <td className="td text-ink-2" title={timestampUtc(o.captured_at_utc)}>{timestamp(o.captured_at_utc)}</td>
              <td className="td text-right font-medium tabular-nums">
                {money(o.price_total, o.currency)}
                {o.original_currency !== o.currency && (
                  <div className="text-[11px] font-normal text-ink-3">{money(o.original_price, o.original_currency)}</div>
                )}
              </td>
              <td className="td"><SourceBadge source={o.source} assumed={o.profile_assumed} /></td>
              <td className="td text-ink-2">{label(o.baggage_profile)}</td>
              <td className="td text-ink-2">{label(o.fare_product)}</td>
              <td className="td">{o.discount_club === "member" ? <MemberBadge /> : <span className="text-ink-2">{label(o.discount_club)}</span>}</td>
              <td className="td text-right tabular-nums text-ink-2">{o.lead_time_days}</td>
              <td className="td">{o.source_url ? <a className="text-accent-ink hover:underline" href={o.source_url} target="_blank" rel="noopener noreferrer">source ↗</a> : <span className="text-ink-3">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Detail({ d }: { d: FlightDetail }) {
  const f = d.flight;
  return (
    <>
      <DemoWatermark show={d.demo} />
      <PageHeader
        title={`${f.flight_number} · ${f.origin} → ${f.destination}`}
        subtitle={
          <>
            {f.airline} · {dateLong(f.flight_date)} · departs {localTime(f.scheduled_departure_local)} {tzCity(f.origin_tz)} time,
            arrives {localTime(f.scheduled_arrival_local)} {tzCity(f.destination_tz)} time · schedule {f.schedule_status.replace(/_/g, " ")}
          </>
        }
        actions={d.booking_links.map((b) => (
          <a key={b.url} className="btn-ghost" href={b.url} target="_blank" rel="noopener noreferrer" title={b.note}>{b.label} ↗</a>
        ))}
      />
      {d.analysis.profiles.length === 0 ? (
        <Empty title="No observations for this flight yet">Record one on the Dashboard or import a CSV in Price History.</Empty>
      ) : (
        <div className="space-y-6">
          {d.analysis.note && <Notice>{d.analysis.note}</Notice>}
          {d.analysis.profiles.map((p) => <ProfileBlock key={p.profile_label} p={p} obs={d.observations} />)}
          <Card title={`All observations (${d.observations.length})`}>
            <ObservationTable obs={d.observations} />
          </Card>
        </div>
      )}
      <div className="mt-6">
        <Notice tone="warn">
          Fares shown are past observations and may have changed. Verify the final price including baggage and fees on the
          official airline site. FareWatch never books or pays.
        </Notice>
      </div>
    </>
  );
}

export default function FlightDetails() {
  const { id } = useParams();
  const nav = useNavigate();
  const flights = useAsync(() => api.flights());
  const targetIds = (flights.data ?? []).filter((f) => f.is_target).map((f) => f.id);
  const current = id ? Number(id) : null;
  const detail = useAsync(() => (current ? api.flight(current) : Promise.resolve(null)), [current]);
  const outboundId = targetIds[0];
  const returnId = targetIds[1];

  if (flights.loading && !flights.data) return <Loading />;
  if (flights.error) return <ErrorBox message={flights.error} onRetry={flights.reload} />;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        {(flights.data ?? []).filter((f) => f.is_target).map((f) => (
          <Link key={f.id} to={`/flights/${f.id}`}
            className={`btn ${current === f.id ? "bg-raised text-ink shadow-card" : "text-ink-2 ring-1 ring-hair hover:text-ink"}`}>
            {f.direction === "outbound" ? "Outbound" : "Return"} · {f.flight_number}
          </Link>
        ))}
        <select className="input w-auto" value={current ?? ""} onChange={(e) => nav(`/flights/${e.target.value}`)} aria-label="Other flight">
          <option value="" disabled>Other flights…</option>
          {(flights.data ?? []).map((f) => (
            <option key={f.id} value={f.id}>{f.flight_number} {f.origin}→{f.destination} {f.flight_date}</option>
          ))}
        </select>
      </div>
      {!current ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {[outboundId, returnId].filter(Boolean).map((fid) => (
            <Link key={fid} to={`/flights/${fid}`} className="card p-5 hover:ring-1 hover:ring-accent">
              <div className="text-sm font-medium text-ink">
                {fid === outboundId ? "Outbound chart" : "Return chart"}
              </div>
              <div className="text-xs text-ink-3">Open separate price history for this leg</div>
            </Link>
          ))}
        </div>
      ) : detail.loading && !detail.data ? (
        <Loading />
      ) : detail.error ? (
        <ErrorBox message={detail.error} onRetry={detail.reload} />
      ) : detail.data ? (
        <Detail d={detail.data} />
      ) : null}
    </>
  );
}
