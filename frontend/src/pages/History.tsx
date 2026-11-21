import { useRef, useState } from "react";
import { Card, DemoWatermark, Empty, ErrorBox, Loading, MemberBadge, Notice, PageHeader, SourceBadge } from "../components/ui";
import { api, type ImportReport } from "../lib/api";
import { label, money, timestamp, timestampUtc } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function History() {
  const [filters, setFilters] = useState({ source: "", origin: "", destination: "", flight_date_from: "", flight_date_to: "" });
  const [sort, setSort] = useState("captured_at");
  const [order, setOrder] = useState("desc");
  const { data, error, loading, reload } = useAsync(
    () => api.observations({ ...filters, sort, order }),
    [JSON.stringify(filters), sort, order],
  );
  const fileRef = useRef<HTMLInputElement>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [importErr, setImportErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function doImport(dryRun: boolean) {
    const file = fileRef.current?.files?.[0];
    if (!file) return setImportErr("Choose a CSV file first.");
    setBusy(true);
    setImportErr(null);
    try {
      setReport(await api.importCsv(file, dryRun));
      if (!dryRun) reload();
    } catch (e) {
      setImportErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("Delete this observation permanently?")) return;
    await api.deleteObservation(id);
    reload();
  }

  const set = (k: keyof typeof filters) => (e: { target: { value: string } }) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <>
      <DemoWatermark show={!!data?.demo} />
      <PageHeader
        title="Price History"
        subtitle="Every recorded observation, with its source. Demo fixtures are never exported."
        actions={<a className="btn-ghost" href="/api/observations/export.csv">Export CSV</a>}
      />

      <Card title="Filters" className="mb-6">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-7">
          <label><span className="field-label">Source</span>
            <select className="input" value={filters.source} onChange={set("source")}>
              <option value="">All</option><option value="manual">Manual</option>
              <option value="serpapi_google_flights">SerpApi (live)</option>
              <option value="serpapi_price_history">Google price history</option><option value="csv_import">CSV import</option>
            </select>
          </label>
          <label><span className="field-label">From</span><input className="input uppercase" maxLength={3} placeholder="SJJ" value={filters.origin} onChange={set("origin")} /></label>
          <label><span className="field-label">To</span><input className="input uppercase" maxLength={3} placeholder="FCO" value={filters.destination} onChange={set("destination")} /></label>
          <label><span className="field-label">Travel from</span><input className="input" type="date" value={filters.flight_date_from} onChange={set("flight_date_from")} /></label>
          <label><span className="field-label">Travel to</span><input className="input" type="date" value={filters.flight_date_to} onChange={set("flight_date_to")} /></label>
          <label><span className="field-label">Sort by</span>
            <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="captured_at">Observed time</option><option value="price">Price</option><option value="flight_date">Travel date</option>
            </select>
          </label>
          <label><span className="field-label">Order</span>
            <select className="input" value={order} onChange={(e) => setOrder(e.target.value)}>
              <option value="desc">Descending</option><option value="asc">Ascending</option>
            </select>
          </label>
        </div>
      </Card>

      <Card title={data ? `Observations (${data.items.length})` : "Observations"} className="mb-6">
        {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : !data?.items.length ? (
          <Empty title="No observations yet">Record a fare on the Dashboard or import a CSV below.</Empty>
        ) : (
          <div className="-mx-5 overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-hair"><tr>
                <th className="th">Observed</th><th className="th">Flight</th><th className="th">Travel date</th>
                <th className="th text-right">Price</th><th className="th">Source</th><th className="th">Verification</th>
                <th className="th">Baggage</th><th className="th">Club</th><th className="th">Taxes incl.</th><th className="th" />
              </tr></thead>
              <tbody className="divide-y divide-hair">
                {data.items.map((o) => (
                  <tr key={o.id}>
                    <td className="td text-ink-2" title={timestampUtc(o.captured_at_utc)}>{timestamp(o.captured_at_utc)}</td>
                    <td className="td"><span className="font-medium">{o.flight_number}</span> <span className="text-ink-3">{o.origin}→{o.destination}</span></td>
                    <td className="td text-ink-2">{o.flight_date}</td>
                    <td className="td text-right font-medium tabular-nums">{money(o.price_total, o.currency)}
                      {o.fx_source && <div className="text-[11px] font-normal text-ink-3" title={o.fx_source}>from {money(o.original_price, o.original_currency)}</div>}
                    </td>
                    <td className="td"><SourceBadge source={o.source} assumed={o.profile_assumed} /></td>
                    <td className="td text-ink-2">{o.verification.replace(/_/g, " ")}</td>
                    <td className="td text-ink-2">{label(o.baggage_profile)}</td>
                    <td className="td">{o.discount_club === "member" ? <MemberBadge /> : <span className="text-ink-2">{label(o.discount_club)}</span>}</td>
                    <td className="td text-ink-2">{label(o.taxes_fees_included)}</td>
                    <td className="td text-right">{!o.is_demo && <button className="text-xs text-ink-3 hover:text-bad" onClick={() => remove(o.id)}>Delete</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Import CSV">
        <div className="space-y-4">
          <p className="text-sm text-ink-2">
            Required columns: <code className="text-xs">flight_number, origin, destination, flight_date, captured_at_utc, price_total, currency</code>.
            Optional: passengers, fare_product, baggage_profile, taxes_fees_included, discount_club, airline,
            scheduled_departure_local, scheduled_arrival_local, source_url, booking_url, notes. Timestamps need a timezone
            (e.g. <code className="text-xs">2026-11-20T08:00:00Z</code>). Imported rows are marked unverified.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="text-sm text-ink-2 file:mr-3 file:rounded-lg file:border-0 file:bg-raised file:px-3 file:py-2 file:text-sm file:text-ink file:ring-1 file:ring-hair" />
            <button className="btn-ghost" disabled={busy} onClick={() => doImport(true)}>Validate only</button>
            <button className="btn-primary" disabled={busy} onClick={() => doImport(false)}>Import</button>
          </div>
          {importErr && <ErrorBox message={importErr} />}
          {report && (
            <Notice>
              <div className="font-medium">
                {report.dry_run ? "Validation" : "Import"} finished: {report.total_rows} rows, {report.imported} imported,
                {" "}{report.duplicates} duplicates, {report.errors.length} errors.
              </div>
              {report.errors.length > 0 && (
                <ul className="mt-2 max-h-48 list-disc space-y-0.5 overflow-auto pl-5">
                  {report.errors.map((e) => <li key={`${e.row}-${e.error}`}>Row {e.row}: {e.error}</li>)}
                </ul>
              )}
            </Notice>
          )}
        </div>
      </Card>
    </>
  );
}
