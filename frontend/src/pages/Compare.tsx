import { useMemo, useState, type FormEvent } from "react";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { Card, DemoWatermark, Empty, ErrorBox, Loading, MemberBadge, Notice, PageHeader, SourceBadge, Toast } from "../components/ui";
import { api, ApiError, type CompareRow } from "../lib/api";
import { money, timestamp } from "../lib/format";
import { useAsync } from "../lib/useAsync";

type Dir = "SJJ-FCO" | "FCO-SJJ" | "all";
type SortKey = "lead_time_days" | "price_total" | "flight_date" | "captured_at_utc";

function ScatterTip({ active, payload }: { active?: boolean; payload?: { payload: CompareRow }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg bg-raised px-3 py-2 text-xs shadow-card">
      <div className="text-sm font-semibold tabular-nums text-ink">{money(r.price_total, r.currency)}</div>
      <div className="text-ink-2">{r.flight_number} {r.origin}→{r.destination} · {r.flight_date} ({r.travel_weekday})</div>
      <div className="text-ink-3">{r.lead_time_days} days before departure · seen {timestamp(r.captured_at_utc)}</div>
      {r.travel_holiday_name && <div className="text-ink-3">Holiday: {r.travel_holiday_name}</div>}
    </div>
  );
}

function AddFlight({ onAdded }: { onAdded: () => void }) {
  const [form, setForm] = useState({ origin: "SJJ", destination: "FCO", flight_date: "2026-12-30", flight_number: "W4 6160", dep: "", arr: "" });
  const [msg, setMsg] = useState<{ m: string; t: "good" | "bad" } | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const f = await api.createFlight({
        origin: form.origin, destination: form.destination, flight_date: form.flight_date, flight_number: form.flight_number,
        scheduled_departure_local: form.dep || null, scheduled_arrival_local: form.arr || null,
      });
      setMsg({ m: `Flight ${f.flight_number} on ${f.flight_date} is available in the manual entry form.`, t: "good" });
      onAdded();
    } catch (err) {
      setMsg({ m: (err as ApiError).message, t: "bad" });
    }
  }
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-6">
      <label><span className="field-label">From</span><input className="input uppercase" maxLength={3} value={form.origin} onChange={set("origin")} /></label>
      <label><span className="field-label">To</span><input className="input uppercase" maxLength={3} value={form.destination} onChange={set("destination")} /></label>
      <label><span className="field-label">Date</span><input className="input" type="date" min="2026-11-01" max="2027-01-31" value={form.flight_date} onChange={set("flight_date")} /></label>
      <label><span className="field-label">Flight no.</span><input className="input" value={form.flight_number} onChange={set("flight_number")} /></label>
      <label><span className="field-label">Dep (local)</span><input className="input" type="time" value={form.dep} onChange={set("dep")} /></label>
      <label><span className="field-label">Arr (local)</span><input className="input" type="time" value={form.arr} onChange={set("arr")} /></label>
      <div className="sm:col-span-6 flex flex-col gap-3">
        {msg && <Toast message={msg.m} tone={msg.t} onClose={() => setMsg(null)} />}
        <button className="btn-ghost w-fit">Add comparison flight</button>
      </div>
    </form>
  );
}

export default function Compare() {
  const [dir, setDir] = useState<Dir>("SJJ-FCO");
  const [comparableOnly, setComparableOnly] = useState(true);
  const [month, setMonth] = useState("all");
  const [sort, setSort] = useState<{ k: SortKey; asc: boolean }>({ k: "lead_time_days", asc: true });
  const [o, d] = dir === "all" ? [undefined, undefined] : dir.split("-");
  const { data, error, loading, reload } = useAsync(() => api.compare(o, d), [dir]);

  const rows = useMemo(() => {
    let r = data?.rows ?? [];
    if (comparableOnly) r = r.filter((x) => x.matches_preferences);
    if (month !== "all") r = r.filter((x) => x.flight_date.startsWith(month));
    const sign = sort.asc ? 1 : -1;
    return [...r].sort((a, b) => {
      const va = sort.k === "price_total" ? Number(a.price_total) : a[sort.k];
      const vb = sort.k === "price_total" ? Number(b.price_total) : b[sort.k];
      return va < vb ? -sign : va > vb ? sign : 0;
    });
  }, [data, comparableOnly, month, sort]);

  const target = rows.filter((r) => r.is_target && r.lead_time_days >= 0).map((r) => ({ ...r, x: r.lead_time_days, y: Number(r.price_total) }));
  const other = rows.filter((r) => !r.is_target && r.lead_time_days >= 0).map((r) => ({ ...r, x: r.lead_time_days, y: Number(r.price_total) }));
  const cur = rows[0]?.currency ?? "EUR";

  const th = (k: SortKey, text: string, right = false) => (
    <th className={`th ${right ? "text-right" : ""}`}>
      <button className="uppercase tracking-wide hover:text-ink" onClick={() => setSort({ k, asc: sort.k === k ? !sort.asc : true })}>
        {text}{sort.k === k ? (sort.asc ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  return (
    <>
      <DemoWatermark show={!!data?.demo} />
      <PageHeader title="Compare Flights" subtitle="Nearby departures (Nov 2026 – Jan 2027) in both directions. Each flight keeps its own identity; this is a cross-flight view, separate from exact-flight history." />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg p-1 ring-1 ring-hair" role="group" aria-label="Direction">
          {(["SJJ-FCO", "FCO-SJJ", "all"] as Dir[]).map((v) => (
            <button key={v} onClick={() => setDir(v)} aria-pressed={dir === v}
              className={`rounded-md px-3 py-1.5 text-sm ${dir === v ? "bg-raised font-medium text-ink shadow-card" : "text-ink-2"}`}>
              {v === "all" ? "Both" : v.replace("-", " → ")}
            </button>
          ))}
        </div>
        <select className="input w-auto" value={month} onChange={(e) => setMonth(e.target.value)} aria-label="Travel month">
          <option value="all">All travel months</option>
          <option value="2026-11">November 2026</option>
          <option value="2026-12">December 2026</option>
          <option value="2027-01">January 2027</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" checked={comparableOnly} onChange={(e) => setComparableOnly(e.target.checked)} />
          Only my comparison profile
        </label>
      </div>

      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data && (
        <div className="space-y-6">
          <Card title="Price vs days before departure">
            {target.length + other.length === 0 ? (
              <Empty title="No observations match these filters">
                Add comparison flights below and record fares, or let the collector sample nearby dates (Settings).
              </Empty>
            ) : (
              <>
                <div className="mb-3 flex flex-wrap gap-4 text-xs text-ink-2" aria-label="Legend">
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--series-1)" }} />Target flights ({target.length})</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rotate-45" style={{ background: "var(--series-2)" }} />Other dates / flights ({other.length})</span>
                </div>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 8, right: 12, bottom: 20, left: 4 }}>
                      <CartesianGrid stroke="var(--grid)" vertical={false} />
                      <XAxis type="number" dataKey="x" name="Days before departure" reversed
                        tick={{ fill: "var(--chart-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--axis)" }} tickLine={false}
                        label={{ value: "days before departure", position: "insideBottom", offset: -12, fill: "var(--chart-muted)", fontSize: 11 }} />
                      <YAxis type="number" dataKey="y" name="Price" domain={["auto", "auto"]} width={64}
                        tickFormatter={(v) => money(String(v), cur).replace(/\.00$/, "")}
                        tick={{ fill: "var(--chart-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <ZAxis range={[60, 60]} />
                      <Tooltip content={<ScatterTip />} cursor={{ strokeDasharray: "3 3", stroke: "var(--axis)" }} />
                      <Scatter name="Other" data={other} fill="var(--series-2)" shape="diamond" stroke="var(--surface)" strokeWidth={1.5} isAnimationActive={false} />
                      <Scatter name="Target" data={target} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={1.5} isAnimationActive={false} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
            <div className="mt-3"><Notice>{data.note}</Notice></div>
          </Card>

          <Card title="Median by lead-time bucket (your profile, all flights)">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {data.lead_time_buckets.map((b) => (
                <div key={b.bucket} className="rounded-lg px-3 py-2 ring-1 ring-hair">
                  <div className="text-xs text-ink-3">{b.bucket} days</div>
                  <div className="text-lg font-semibold tabular-nums">{b.median ? money(b.median, cur) : "—"}</div>
                  <div className="text-[11px] text-ink-3">{b.count} quotes · {b.flights} flights</div>
                </div>
              ))}
            </div>
          </Card>

          <Card title={`Observations (${rows.length})`}>
            {rows.length === 0 ? <Empty title="Nothing to show" /> : (
              <div className="-mx-5 overflow-x-auto">
                <table className="min-w-full">
                  <thead className="border-b border-hair"><tr>
                    <th className="th">Flight</th>{th("flight_date", "Travel date")}<th className="th">Travel day</th>
                    {th("lead_time_days", "Lead (d)", true)}{th("price_total", "Price", true)}<th className="th">Source</th>
                    {th("captured_at_utc", "Observed")}<th className="th">Obs. day</th><th className="th">Holiday</th>
                  </tr></thead>
                  <tbody className="divide-y divide-hair">
                    {rows.map((r) => (
                      <tr key={r.observation_id}>
                        <td className="td"><span className="font-medium">{r.flight_number}</span> <span className="text-ink-3">{r.origin}→{r.destination}</span>{r.is_target && <span className="ml-1.5 text-[11px] text-accent-ink">target</span>}</td>
                        <td className="td text-ink-2">{r.flight_date}</td>
                        <td className="td text-ink-2">{r.travel_weekday}</td>
                        <td className="td text-right tabular-nums">{r.lead_time_days}</td>
                        <td className="td text-right font-medium tabular-nums">{money(r.price_total, r.currency)}{r.discount_club === "member" && <span className="ml-1"><MemberBadge /></span>}</td>
                        <td className="td"><SourceBadge source={r.source} /></td>
                        <td className="td text-ink-2">{timestamp(r.captured_at_utc)}</td>
                        <td className="td text-ink-2">{r.observation_weekday}</td>
                        <td className="td text-ink-2">{r.travel_holiday_name ?? (r.travel_festive_window ? "festive period" : "—")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="Add a comparison flight">
            <p className="mb-3 text-xs text-ink-3">Creates a flight identity so you can record fares for it. Only enter flights you have seen listed.</p>
            <AddFlight onAdded={reload} />
          </Card>
        </div>
      )}
    </>
  );
}
