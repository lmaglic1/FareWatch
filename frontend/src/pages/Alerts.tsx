import { useState, type FormEvent } from "react";
import { Card, Empty, ErrorBox, Loading, Notice, PageHeader, Toast } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { label, money, timestamp, timestampUtc } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Alerts() {
  const flights = useAsync(() => api.flights());
  const rules = useAsync(() => api.alertRules());
  const events = useAsync(() => api.alertEvents());
  const settings = useAsync(() => api.settings());
  const [form, setForm] = useState({ flight_id: 0, kind: "threshold", threshold: "", pct_drop: "10", baggage_profile: "under_seat_only", discount_club: "public", email: false });
  const [msg, setMsg] = useState<{ m: string; t: "good" | "bad" } | null>(null);

  const flightId = form.flight_id || flights.data?.find((f) => f.is_target)?.id || 0;
  const currency = settings.data?.preferences.display_currency ?? "EUR";

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addAlertRule({
        flight_id: flightId, kind: form.kind, currency,
        threshold: form.kind === "threshold" ? form.threshold : null,
        pct_drop: form.kind === "pct_drop" ? form.pct_drop : null,
        baggage_profile: form.baggage_profile, discount_club: form.discount_club, email: form.email,
      });
      setMsg({ m: "Alert rule created. It is checked whenever a new comparable observation is recorded.", t: "good" });
      rules.reload();
    } catch (err) {
      const a = err as ApiError;
      setMsg({ m: a.details.length ? a.details.map((d) => d.message).join("; ") : a.message, t: "bad" });
    }
  }

  return (
    <>
      <PageHeader title="Alerts" subtitle="Local alerts when a comparable fare reaches your threshold or drops sharply. Identical repeated quotes are de-duplicated. Demo data never triggers alerts." />
      <div className="grid gap-6 lg:grid-cols-5">
        <Card title="New alert rule" className="lg:col-span-2">
          {flights.loading ? <Loading /> : flights.error ? <ErrorBox message={flights.error} /> : (
            <form onSubmit={submit} className="space-y-3">
              <label className="block"><span className="field-label">Flight</span>
                <select className="input" value={flightId} onChange={(e) => setForm({ ...form, flight_id: Number(e.target.value) })}>
                  {flights.data?.map((f) => <option key={f.id} value={f.id}>{f.flight_number} {f.origin}→{f.destination} {f.flight_date}</option>)}
                </select>
              </label>
              <label className="block"><span className="field-label">Type</span>
                <select className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                  <option value="threshold">Price at or below</option>
                  <option value="pct_drop">Drop vs previous comparable quote</option>
                </select>
              </label>
              {form.kind === "threshold" ? (
                <label className="block"><span className="field-label">Threshold ({currency}, total)</span>
                  <input className="input" required inputMode="decimal" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} />
                </label>
              ) : (
                <label className="block"><span className="field-label">Minimum drop (%)</span>
                  <input className="input" required inputMode="decimal" value={form.pct_drop} onChange={(e) => setForm({ ...form, pct_drop: e.target.value })} />
                </label>
              )}
              <div className="grid grid-cols-2 gap-3">
                <label><span className="field-label">Baggage profile</span>
                  <select className="input" value={form.baggage_profile} onChange={(e) => setForm({ ...form, baggage_profile: e.target.value })}>
                    <option value="under_seat_only">Under-seat only</option><option value="priority_trolley">Priority + trolley</option><option value="checked_bag">Checked bag</option>
                  </select>
                </label>
                <label><span className="field-label">Fare type</span>
                  <select className="input" value={form.discount_club} onChange={(e) => setForm({ ...form, discount_club: e.target.value })}>
                    <option value="public">Public</option><option value="member">Discount Club member</option>
                  </select>
                </label>
              </div>
              <label className={`flex items-center gap-2 text-sm ${settings.data?.email_configured ? "text-ink-2" : "text-ink-3"}`}>
                <input type="checkbox" disabled={!settings.data?.email_configured} checked={form.email} onChange={(e) => setForm({ ...form, email: e.target.checked })} />
                Also send email {settings.data?.email_configured ? "" : "(not configured: see README)"}
              </label>
              {msg && <Toast message={msg.m} tone={msg.t} onClose={() => setMsg(null)} />}
              <button className="btn-primary">Create rule</button>
            </form>
          )}
        </Card>

        <Card title="Active rules" className="lg:col-span-3">
          {rules.loading && !rules.data ? <Loading /> : rules.error ? <ErrorBox message={rules.error} /> : !rules.data?.length ? (
            <Empty title="No alert rules">Create one to be notified on this dashboard.</Empty>
          ) : (
            <ul className="divide-y divide-hair">
              {rules.data.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">
                      {r.kind === "threshold" ? `≤ ${money(r.threshold, r.currency)}` : `drop ≥ ${r.pct_drop}%`}
                      <span className="ml-2 font-normal text-ink-2">{r.flight}</span>
                    </div>
                    <div className="text-xs text-ink-3">{label(r.baggage_profile)} · {label(r.discount_club)}{r.email ? " · email" : ""}</div>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-ghost" onClick={async () => { await api.toggleAlertRule(r.id, !r.active); rules.reload(); }}>
                      {r.active ? "Pause" : "Resume"}
                    </button>
                    <button className="btn-danger" onClick={async () => { await api.deleteAlertRule(r.id); rules.reload(); events.reload(); }}>Delete</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Alert history" className="mt-6">
        {events.loading && !events.data ? <Loading /> : events.error ? <ErrorBox message={events.error} /> : !events.data?.length ? (
          <Empty title="No alerts triggered yet" />
        ) : (
          <ul className="divide-y divide-hair">
            {events.data.map((e) => (
              <li key={e.id} className={`flex flex-wrap items-start justify-between gap-3 py-3 ${e.acknowledged ? "opacity-60" : ""}`}>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-ink-2">
                    <span title={timestampUtc(e.triggered_at_utc)}>{timestamp(e.triggered_at_utc)}</span> · {e.flight}
                    {e.email_status !== "not_requested" && <span className="ml-2 text-ink-3">email: {e.email_status.replace("_", " ")}</span>}
                  </div>
                  <div className="mt-0.5 text-sm text-ink">{e.message}</div>
                </div>
                {!e.acknowledged && <button className="btn-ghost" onClick={async () => { await api.ackAlert(e.id); events.reload(); }}>Mark seen</button>}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4"><Notice tone="warn">An alert means a recorded quote met your rule. Prices change; re-check on the official site before buying.</Notice></div>
      </Card>
    </>
  );
}
