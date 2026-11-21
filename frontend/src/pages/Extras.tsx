import { useState, type FormEvent } from "react";
import { Card, DemoWatermark, Empty, ErrorBox, Loading, Notice, PageHeader, SourceBadge, Toast } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { money, timestamp } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const ITEMS: Record<string, string> = {
  under_seat_bag: "Under-seat bag",
  priority_trolley: "Priority & cabin trolley",
  checked_bag_10kg: "Checked bag 10 kg",
  checked_bag_20kg: "Checked bag 20 kg",
  checked_bag_32kg: "Checked bag 32 kg",
  discount_club_membership: "Wizz Discount Club membership",
};

function errText(e: unknown) {
  const a = e as ApiError;
  return a.details?.length ? a.details.map((d) => `${d.field}: ${d.message}`).join("; ") : a.message;
}

export default function Extras() {
  const flights = useAsync(() => api.flights());
  const cmp = useAsync(() => api.feeComparison());
  const fees = useAsync(() => api.fees());
  const promos = useAsync(() => api.promotions());
  const [fee, setFee] = useState({ flight_id: "", item: "priority_trolley", price: "", currency: "EUR", per: "per_leg", source_url: "", notes: "" });
  const [promo, setPromo] = useState({ title: "", announced_date: "", booking_deadline: "", travel_start: "", travel_end: "", discount_description: "", excluded_dates: "", member_only: false, source_url: "", notes: "" });
  const [msg, setMsg] = useState<{ m: string; t: "good" | "bad" } | null>(null);
  const [pmsg, setPmsg] = useState<{ m: string; t: "good" | "bad" } | null>(null);

  async function addFee(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addFee({
        ...fee, flight_id: fee.flight_id ? Number(fee.flight_id) : null, source_url: fee.source_url || null, notes: fee.notes || null,
        per: fee.item === "discount_club_membership" ? "per_year" : fee.per,
      });
      setMsg({ m: "Fee recorded.", t: "good" });
      fees.reload(); cmp.reload();
    } catch (err) { setMsg({ m: errText(err), t: "bad" }); }
  }

  async function addPromo(e: FormEvent) {
    e.preventDefault();
    const body = Object.fromEntries(Object.entries(promo).map(([k, v]) => [k, v === "" ? null : v]));
    try {
      await api.addPromotion(body);
      setPmsg({ m: "Promotion logged. It is not assumed to apply to your flights.", t: "good" });
      promos.reload();
    } catch (err) { setPmsg({ m: errText(err), t: "bad" }); }
  }

  return (
    <>
      <DemoWatermark show={!!cmp.data?.demo} />
      <PageHeader title="Bags & Promotions" subtitle="Compare fare bundles using baggage fees you actually recorded, and keep a log of announced promotions." />

      <Card title="Fare + baggage comparison (target flights)" className="mb-6">
        {cmp.loading && !cmp.data ? <Loading /> : cmp.error ? <ErrorBox message={cmp.error} /> : cmp.data && (
          <div className="space-y-5">
            <div className="grid gap-5 lg:grid-cols-2">
              {cmp.data.legs.map((l) => (
                <div key={l.flight_id} className="rounded-lg ring-1 ring-hair">
                  <div className="border-b border-hair px-4 py-2.5 text-sm font-medium">{l.flight}</div>
                  <table className="min-w-full">
                    <tbody className="divide-y divide-hair">
                      {l.options.map((o) => (
                        <tr key={o.bundle}>
                          <td className="td text-ink-2">{o.label}</td>
                          <td className="td text-right text-xs text-ink-3">
                            {o.base_fare === null ? "no base fare" : o.addon_known ? `fare ${money(o.base_fare, cmp.data!.currency)} + ${money(o.addon_fee, cmp.data!.currency)}` : "fee unknown"}
                          </td>
                          <td className="td text-right font-semibold tabular-nums">
                            {o.total ? money(o.total, cmp.data!.currency) : <span className="font-normal text-ink-3">Unknown</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="flex items-center gap-2 px-4 py-2 text-[11px] text-ink-3">
                    {l.base_source ? <>Base fare <SourceBadge source={l.base_source} /> {timestamp(l.base_observed_at)}</> : "Record a public under-seat-only fare to fill this table."}
                  </div>
                </div>
              ))}
            </div>
            <div className="text-sm text-ink-2">
              Discount Club membership (separate cost):{" "}
              {cmp.data.discount_club_membership
                ? <strong>{money(cmp.data.discount_club_membership.price, cmp.data.discount_club_membership.currency)} / year</strong>
                : <span className="text-ink-3">not recorded</span>}
            </div>
            <Notice>{cmp.data.note}</Notice>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Record an add-on fee">
          <form onSubmit={addFee} className="grid gap-3 sm:grid-cols-2">
            <label><span className="field-label">Item</span>
              <select className="input" value={fee.item} onChange={(e) => setFee({ ...fee, item: e.target.value })}>
                {Object.entries(ITEMS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label><span className="field-label">Applies to</span>
              <select className="input" value={fee.flight_id} onChange={(e) => setFee({ ...fee, flight_id: e.target.value })}>
                <option value="">Any flight (general)</option>
                {flights.data?.filter((f) => f.is_target).map((f) => <option key={f.id} value={f.id}>{f.flight_number} {f.flight_date}</option>)}
              </select>
            </label>
            <label><span className="field-label">Price</span><input className="input" required inputMode="decimal" value={fee.price} onChange={(e) => setFee({ ...fee, price: e.target.value })} /></label>
            <label><span className="field-label">Currency</span>
              <select className="input" value={fee.currency} onChange={(e) => setFee({ ...fee, currency: e.target.value })}>
                {["EUR", "BAM", "USD", "GBP", "HUF"].map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="sm:col-span-2"><span className="field-label">Source URL</span><input className="input" type="url" value={fee.source_url} onChange={(e) => setFee({ ...fee, source_url: e.target.value })} /></label>
            <div className="sm:col-span-2 space-y-3">
              {msg && <Toast message={msg.m} tone={msg.t} onClose={() => setMsg(null)} />}
              <button className="btn-primary">Save fee</button>
            </div>
          </form>
          <div className="mt-5">
            {fees.data?.length ? (
              <ul className="divide-y divide-hair text-sm">
                {fees.data.map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2 py-2">
                    <span className="text-ink-2">{ITEMS[f.item] ?? f.item} <span className="text-ink-3">· {timestamp(f.observed_at_utc)}</span></span>
                    <span className="flex items-center gap-3">
                      <span className="font-medium tabular-nums">{money(f.price, f.currency)}</span>
                      <button className="text-xs text-ink-3 hover:text-bad" onClick={async () => { await api.deleteFee(f.id); fees.reload(); cmp.reload(); }}>Delete</button>
                    </span>
                  </li>
                ))}
              </ul>
            ) : <Empty title="No fees recorded" />}
          </div>
        </Card>

        <Card title="Log a promotion">
          <form onSubmit={addPromo} className="grid gap-3 sm:grid-cols-2">
            <label className="sm:col-span-2"><span className="field-label">Title</span><input className="input" required value={promo.title} onChange={(e) => setPromo({ ...promo, title: e.target.value })} /></label>
            <label className="sm:col-span-2"><span className="field-label">Discount (as announced)</span><input className="input" required placeholder="e.g. 20% off selected routes" value={promo.discount_description} onChange={(e) => setPromo({ ...promo, discount_description: e.target.value })} /></label>
            <label><span className="field-label">Announced</span><input className="input" type="date" value={promo.announced_date} onChange={(e) => setPromo({ ...promo, announced_date: e.target.value })} /></label>
            <label><span className="field-label">Booking deadline</span><input className="input" type="date" value={promo.booking_deadline} onChange={(e) => setPromo({ ...promo, booking_deadline: e.target.value })} /></label>
            <label><span className="field-label">Travel from</span><input className="input" type="date" value={promo.travel_start} onChange={(e) => setPromo({ ...promo, travel_start: e.target.value })} /></label>
            <label><span className="field-label">Travel until</span><input className="input" type="date" value={promo.travel_end} onChange={(e) => setPromo({ ...promo, travel_end: e.target.value })} /></label>
            <label className="sm:col-span-2"><span className="field-label">Excluded dates</span><input className="input" value={promo.excluded_dates} onChange={(e) => setPromo({ ...promo, excluded_dates: e.target.value })} /></label>
            <label className="sm:col-span-2"><span className="field-label">Source URL</span><input className="input" type="url" value={promo.source_url} onChange={(e) => setPromo({ ...promo, source_url: e.target.value })} /></label>
            <label className="flex items-center gap-2 text-sm text-ink-2 sm:col-span-2">
              <input type="checkbox" checked={promo.member_only} onChange={(e) => setPromo({ ...promo, member_only: e.target.checked })} /> Discount Club members only
            </label>
            <div className="sm:col-span-2 space-y-3">
              {pmsg && <Toast message={pmsg.m} tone={pmsg.t} onClose={() => setPmsg(null)} />}
              <button className="btn-primary">Save promotion</button>
            </div>
          </form>
          <div className="mt-5">
            {promos.loading && !promos.data ? <Loading /> : !promos.data?.length ? <Empty title="No promotions logged" /> : (
              <ul className="divide-y divide-hair">
                {promos.data.map((p) => (
                  <li key={p.id} className="py-3 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-medium text-ink">{p.title} {p.member_only && <span className="text-xs text-warn">(members only)</span>}</div>
                        <div className="text-ink-2">{p.discount_description}</div>
                        <div className="text-xs text-ink-3">
                          Book by {p.booking_deadline ?? "?"} · travel {p.travel_start ?? "?"} – {p.travel_end ?? "?"}
                          {p.excluded_dates && ` · excluded: ${p.excluded_dates}`}
                          {p.source_url && <> · <a className="text-accent-ink hover:underline" href={p.source_url} target="_blank" rel="noopener noreferrer">source ↗</a></>}
                        </div>
                      </div>
                      <button className="text-xs text-ink-3 hover:text-bad" onClick={async () => { await api.deletePromotion(p.id); promos.reload(); }}>Delete</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3"><Notice>Logged promotions are not assumed to apply to your flights. Check eligibility and excluded dates on the airline's official site.</Notice></div>
          </div>
        </Card>
      </div>
    </>
  );
}
