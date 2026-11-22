import { PriceChart } from "./PriceChart";
import { Card, Empty, MemberBadge, SourceBadge, Stat, StatusPill } from "./ui";
import type { Observation, ProfileAnalysis } from "../lib/api";
import { label, money, pct, timestamp, timestampUtc } from "../lib/format";

function sameProfile(o: Observation, p: ProfileAnalysis["profile"]) {
  return o.currency === p.currency && o.passengers === p.passengers && o.fare_product === p.fare_product &&
    o.baggage_profile === p.baggage_profile && o.taxes_fees_included === p.taxes_fees_included &&
    o.discount_club === p.discount_club;
}

export function ProfileBlock({ p, obs }: { p: ProfileAnalysis; obs: Observation[] }) {
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

export function ObservationTable({ obs }: { obs: Observation[] }) {
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

