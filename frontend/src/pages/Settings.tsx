import { useEffect, useState } from "react";
import { Card, ErrorBox, Loading, Notice, PageHeader, Toast } from "../components/ui";
import { api, ApiError, type Preferences } from "../lib/api";
import { timestamp, timestampUtc } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function Backfill({ onDone, remaining }: { onDone: () => void; remaining: number }) {
  const [count, setCount] = useState(4);
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<string | null>(null);
  async function go() {
    setBusy(true);
    setOut(null);
    try {
      const r = await api.runCollector(true, count);
      setOut(r.ran ? r.results.map((x) => `${x.route} ${"date" in x ? (x as { date?: string }).date ?? "" : ""}: ${x.status.replace(/_/g, " ")} - ${x.message}`).join("\n") : r.reason ?? "Not run");
      onDone();
    } catch (e) {
      setOut((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mt-4 rounded-lg p-4 ring-1 ring-hair">
      <div className="text-sm font-medium text-ink">Import Google price history</div>
      <p className="mt-1 text-xs text-ink-3">
        Each search returns the current price plus Google Flights' recorded daily lowest price for that search over
        roughly the last two months. This checks both target legs, then up to N nearby Nov–Jan dates. Searches
        used: up to 2 + N, limited by today's remaining budget ({remaining}).
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label><span className="field-label">Nearby dates (N)</span>
          <input className="input w-24" type="number" min={1} max={10} value={count} onChange={(e) => setCount(Number(e.target.value))} />
        </label>
        <button className="btn-primary" disabled={busy || remaining < 1} onClick={go}>{busy ? "Importing…" : "Import now"}</button>
      </div>
      {out && <div className="mt-3"><Notice><pre className="whitespace-pre-wrap text-[11px]">{out}</pre></Notice></div>}
    </div>
  );
}

export default function Settings() {
  const s = useAsync(() => api.settings());
  const runs = useAsync(() => api.runs());
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [msg, setMsg] = useState<{ m: string; t: "good" | "bad" } | null>(null);
  const [account, setAccount] = useState<Record<string, unknown> | null>(null);

  useEffect(() => { if (s.data) setPrefs(s.data.preferences); }, [s.data]);

  async function save(changes: Partial<Preferences>) {
    try {
      const p = await api.updateSettings(changes);
      setPrefs(p);
      setMsg({ m: "Settings saved.", t: "good" });
      s.reload();
    } catch (e) {
      setMsg({ m: (e as ApiError).message, t: "bad" });
    }
  }

  if (s.loading && !s.data) return <Loading />;
  if (s.error) return <ErrorBox message={s.error} onRetry={s.reload} />;
  if (!s.data || !prefs) return null;
  const c = s.data.collector;
  const serp = s.data.providers.find((p) => p.name === "serpapi_google_flights");

  return (
    <>
      <PageHeader title="Settings" subtitle="Preferences are stored in the local database. API keys and email credentials live only in your .env file and are never shown here." />
      {msg && <div className="mb-5"><Toast message={msg.m} tone={msg.t} onClose={() => setMsg(null)} /></div>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Data sources">
          <ul className="divide-y divide-hair">
            {s.data.providers.map((p) => (
              <li key={p.name} className="flex items-start justify-between gap-3 py-3">
                <div>
                  <div className="text-sm font-medium text-ink">{p.label}</div>
                  <div className="text-xs text-ink-3">{p.description}</div>
                  {p.last_successful_fetch_utc !== undefined && (
                    <div className="mt-1 text-xs text-ink-3">Last successful fetch: {p.last_successful_fetch_utc ? timestamp(p.last_successful_fetch_utc) : "never"}</div>
                  )}
                </div>
                <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${p.connected ? "bg-good-soft text-good" : "bg-raised text-ink-3 ring-1 ring-hair"}`}>
                  {p.connected ? "● Connected" : "○ Not connected"}
                </span>
              </li>
            ))}
          </ul>
          {serp?.connected && (
            <div className="mt-3 space-y-2">
              <button className="btn-ghost" onClick={async () => setAccount(await api.serpapiAccount())}>Check SerpApi account usage (free)</button>
              {account && <Notice><pre className="whitespace-pre-wrap text-[11px]">{JSON.stringify(account, null, 2)}</pre></Notice>}
            </div>
          )}
          {serp?.connected && <Backfill onDone={() => { s.reload(); runs.reload(); }} remaining={c.budget.remaining_today} />}
          {!serp?.connected && (
            <div className="mt-3"><Notice>To connect SerpApi, put <code>SERPAPI_API_KEY=...</code> in the <code>.env</code> file at the repository root and restart the backend. See README.</Notice></div>
          )}
        </Card>

        <Card title="Comparison profile">
          <div className="grid gap-3 sm:grid-cols-2">
            <label><span className="field-label">Display currency</span>
              <select className="input" value={prefs.display_currency} onChange={(e) => save({ display_currency: e.target.value })}>
                {s.data.currencies.map((c2) => <option key={c2}>{c2}</option>)}
              </select>
            </label>
            <label><span className="field-label">Passengers</span>
              <input className="input" type="number" min={1} max={9} value={prefs.passengers} onChange={(e) => setPrefs({ ...prefs, passengers: Number(e.target.value) })} onBlur={() => save({ passengers: prefs.passengers })} />
            </label>
            <label><span className="field-label">Baggage profile</span>
              <select className="input" value={prefs.baggage_profile} onChange={(e) => save({ baggage_profile: e.target.value })}>
                <option value="under_seat_only">Free under-seat bag only</option>
                <option value="priority_trolley">Priority + cabin trolley</option>
                <option value="checked_bag">Checked bag</option>
              </select>
            </label>
            <label><span className="field-label">Fare type</span>
              <select className="input" value={prefs.discount_club} onChange={(e) => save({ discount_club: e.target.value })}>
                <option value="public">Public fares</option>
                <option value="member">Discount Club member fares</option>
              </select>
            </label>
            <label><span className="field-label">Median threshold (%) - heuristic</span>
              <input className="input" inputMode="decimal" value={prefs.median_threshold_pct} onChange={(e) => setPrefs({ ...prefs, median_threshold_pct: e.target.value })} onBlur={() => save({ median_threshold_pct: prefs.median_threshold_pct })} />
            </label>
            <label><span className="field-label">Minimum quotes for a status</span>
              <input className="input" type="number" min={2} max={100} value={prefs.min_samples_for_status} onChange={(e) => setPrefs({ ...prefs, min_samples_for_status: Number(e.target.value) })} onBlur={() => save({ min_samples_for_status: prefs.min_samples_for_status })} />
            </label>
            <label><span className="field-label">Significant drop (%)</span>
              <input className="input" inputMode="decimal" value={prefs.drop_alert_pct} onChange={(e) => setPrefs({ ...prefs, drop_alert_pct: e.target.value })} onBlur={() => save({ drop_alert_pct: prefs.drop_alert_pct })} />
            </label>
          </div>
          <p className="mt-3 text-xs text-ink-3">Only observations matching currency, passengers, baggage and fare type are compared with each other. The threshold is your own rule of thumb, not a forecast.</p>
        </Card>

        <Card title="Refresh cadence & API budget">
          <div className="mb-4 grid grid-cols-2 gap-4 text-sm">
            <div><div className="text-xs text-ink-3">Scheduled collector</div><div className="font-medium">{c.enabled ? (c.scheduler_running ? "Running" : "Enabled, not running") : "Off (COLLECTOR_ENABLED=false)"}</div></div>
            <div><div className="text-xs text-ink-3">Timezone</div><div className="font-medium">{c.timezone}</div></div>
            <div><div className="text-xs text-ink-3">Queries today</div><div className="font-medium tabular-nums">{c.budget.used_today} / {c.budget.daily_cap}</div></div>
            <div><div className="text-xs text-ink-3">Queries this month</div><div className="font-medium tabular-nums">{c.budget.used_this_month} / {c.budget.monthly_quota}</div></div>
          </div>
          {c.next_runs.length > 0 && <p className="mb-3 text-xs text-ink-3">Next runs: {c.next_runs.map((r) => timestamp(r)).join(", ")}</p>}
          <div className="grid gap-3 sm:grid-cols-3">
            <label><span className="field-label">Check times (local)</span>
              <input className="input" value={prefs.collector_times} onChange={(e) => setPrefs({ ...prefs, collector_times: e.target.value })} onBlur={() => save({ collector_times: prefs.collector_times })} />
            </label>
            <label><span className="field-label">Max queries / day</span>
              <input className="input" type="number" min={0} max={50} value={prefs.max_queries_per_day} onChange={(e) => setPrefs({ ...prefs, max_queries_per_day: Number(e.target.value) })} onBlur={() => save({ max_queries_per_day: prefs.max_queries_per_day })} />
            </label>
            <label><span className="field-label">Min. minutes between checks</span>
              <input className="input" type="number" min={10} max={1440} value={prefs.min_minutes_between_checks} onChange={(e) => setPrefs({ ...prefs, min_minutes_between_checks: Number(e.target.value) })} onBlur={() => save({ min_minutes_between_checks: prefs.min_minutes_between_checks })} />
            </label>
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" checked={prefs.collector_include_comparisons} onChange={(e) => save({ collector_include_comparisons: e.target.checked })} />
            Use spare budget to sample nearby comparison dates
          </label>
          <div className="mt-4"><Notice>The local scheduler only runs while the backend is running. If your computer sleeps or the server stops, checks are skipped, not caught up.</Notice></div>
        </Card>

        <Card title="Demo mode">
          <p className="mb-3 text-sm text-ink-2">
            Demo mode replaces every view with synthetic fixture data, marked with a DEMO watermark, so you can explore the
            interface. Real observations are never mixed with demo data, exported with it, or alerted on.
          </p>
          <div className="flex flex-wrap gap-2">
            {prefs.demo_mode ? (
              <button className="btn-primary" onClick={async () => { await api.clearDemo(); s.reload(); setMsg({ m: "Demo data removed; showing real data.", t: "good" }); }}>Turn off & delete demo data</button>
            ) : (
              <button className="btn-ghost" onClick={() => save({ demo_mode: true })}>Turn on demo mode</button>
            )}
          </div>
        </Card>
      </div>

      <Card title="Collection log" className="mt-6">
        {runs.loading && !runs.data ? <Loading /> : !runs.data?.length ? (
          <p className="text-sm text-ink-3">No provider queries yet.</p>
        ) : (
          <div className="-mx-5 overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-hair"><tr>
                <th className="th">When</th><th className="th">Trigger</th><th className="th">Route / date</th><th className="th">Status</th>
                <th className="th text-right">Queries</th><th className="th text-right">Saved</th><th className="th">Message</th>
              </tr></thead>
              <tbody className="divide-y divide-hair">
                {runs.data.map((r) => (
                  <tr key={r.id}>
                    <td className="td text-ink-2" title={timestampUtc(r.started_at_utc)}>{timestamp(r.started_at_utc)}</td>
                    <td className="td text-ink-2">{r.trigger}</td>
                    <td className="td">{r.origin}→{r.destination} {r.search_date}</td>
                    <td className={`td font-medium ${r.status === "success" ? "text-good" : r.status === "error" ? "text-bad" : "text-ink-2"}`}>{r.status.replace(/_/g, " ")}</td>
                    <td className="td text-right tabular-nums">{r.queries_used}</td>
                    <td className="td text-right tabular-nums">{r.observations_created}</td>
                    <td className="td max-w-md truncate text-ink-3" title={r.message ?? ""}>{r.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
