import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { exploreApi } from "../lib/api";
import { ago, dateLong, money } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Trips() {
  const { data, error, loading, reload } = useAsync(() => exploreApi.trips());

  async function remove(id: number) {
    await exploreApi.removeTrip(id);
    reload();
  }

  const isNewYear = (t: { kind: string; destination: { code: string } | null; origin: { code: string } | null }) =>
    t.kind === "target";

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">My trips</h1>
      <p className="mt-1 mb-6 max-w-2xl text-sm text-ink-2">
        Routes you have searched, with the most recent price recorded. Open one to see its price history.
      </p>

      <Link to="/trips/new-year"
        className="mb-6 flex flex-col gap-1 rounded-xl bg-surface p-5 shadow-card transition hover:ring-1 hover:ring-accent sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-accent-ink">Featured trip</div>
          <div className="text-lg font-semibold text-ink">New Year in Rome</div>
          <div className="text-sm text-ink-2">Sarajevo ⇄ Rome · 31 Dec 2026 – 5 Jan 2027 · both legs, trip total and price status</div>
        </div>
        <span className="text-sm font-medium text-accent-ink">Open trip dashboard →</span>
      </Link>

      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : !data?.length ? (
        <Empty title="No trips yet">Search for a destination on the Explore page to start tracking it.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((t) => {
            const o = t.origin?.code ?? "";
            const d = t.destination?.code ?? "";
            return (
              <div key={t.id} className="flex items-center justify-between gap-3 rounded-xl bg-surface p-4 shadow-card">
                <Link to={`/route/${o}/${d}/${t.date}`} className="min-w-0 flex-1">
                  <div className="truncate font-semibold text-ink">
                    {t.origin?.city ?? o} → {t.destination?.city ?? d}
                    {isNewYear(t) && <span className="ml-2 text-[11px] font-medium text-accent-ink">New Year trip</span>}
                  </div>
                  <div className="text-sm text-ink-2">{dateLong(t.date)}</div>
                  <div className="text-xs text-ink-3">Checked {t.last_checked_utc ? ago(t.last_checked_utc) : "never"}</div>
                </Link>
                <div className="text-right">
                  <div className="text-lg font-semibold tabular-nums">{t.latest_price ? money(t.latest_price, t.latest_currency ?? "EUR") : "—"}</div>
                  {t.latest_flight_number && <div className="text-[11px] text-ink-3">{t.latest_flight_number}</div>}
                  {t.kind === "user" && (
                    <button className="mt-1 text-xs text-ink-3 hover:text-bad" onClick={() => remove(t.id)}>Remove</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
