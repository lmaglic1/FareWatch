import { Card, Loading, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function ForecastPanel() {
  const { data, loading, error } = useAsync(() => api.forecast());
  if (loading) return <Loading />;
  if (error || !data) return <p className="text-sm text-bad">{error}</p>;
  if (data.status === "insufficient_data") {
    return (
      <div className="space-y-2 text-sm text-ink-2">
        <p>{data.message}</p>
        <ul className="list-disc pl-5 text-xs text-ink-3">
          {Object.entries(data.requirements ?? {}).map(([k, v]) => <li key={k}>{k.replace(/_/g, " ")}: {v}</li>)}
        </ul>
      </div>
    );
  }
  return (
    <div className="space-y-2 text-sm text-ink-2">
      <p><strong>Experimental.</strong> {data.method}</p>
      <p>Profile: {data.profile}. Train {data.n_train}, test {data.n_test} observations.</p>
      <p>MAE model {money(data.mae_model)} vs baseline (last price) {money(data.mae_baseline_last_price)} — {data.model_beats_baseline ? "the model beat the baseline on this hold-out." : "the model did NOT beat the naive baseline; do not rely on it."}</p>
      <p>Absolute error band (10th–90th pct): {money(data.abs_error_p10)} – {money(data.abs_error_p90)}</p>
      <p className="text-xs text-ink-3">{data.caveat}</p>
    </div>
  );
}

export default function About() {
  return (
    <>
      <PageHeader title="About the Algorithm" subtitle="What FareWatch measures, what it assumes, and what it cannot know." />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="prose-fw card p-6 lg:col-span-2">
          <h2 style={{ marginTop: 0 }}>Data, not predictions</h2>
          <p>
            Every price in FareWatch is an observation: a fare you saw yourself (manual entry), a row you imported from CSV,
            or a result returned by SerpApi's Google Flights API. Each carries its source, timestamp (stored in UTC) and fare
            assumptions. FareWatch never scrapes Wizz Air, never calls undocumented endpoints and never invents prices. Demo
            fixtures exist only for exploring the interface; they are watermarked and kept apart from real data.
          </p>

          <h2>Comparable means identical assumptions</h2>
          <p>
            Two quotes are compared only if they share currency, passenger count, fare product, baggage profile, taxes/fees
            inclusion and Discount Club status. Member fares need a paid membership and are never mixed with public fares.
            Outbound and return are tracked as separate flights. Their prices are only added together when both legs have
            identical assumptions, and the sum is labelled as two separate quotes, not a bookable round trip.
          </p>

          <h2>Descriptive statistics</h2>
          <ul>
            <li>Min, max, median, average and count of comparable quotes for the exact flight.</li>
            <li>Change versus the previous comparable quote, and drop detection against your drop threshold.</li>
            <li>7-day median, shown only with at least 3 quotes in the last 7 days.</li>
            <li>Rank of the latest quote (1 = cheapest recorded) and volatility (sample standard deviation, ≥ 3 quotes).</li>
            <li>Days to departure, computed from the local date at the origin airport.</li>
          </ul>

          <h2>The status label is a heuristic</h2>
          <p>
            The status compares the latest quote with the median of earlier comparable quotes. If it is at least your threshold
            (default 15%) below, it shows <strong>ATTRACTIVE PRICE</strong>; at least that much above shows <strong>EXPENSIVE RELATIVE TO
            HISTORY</strong>; otherwise <strong>NORMAL RANGE</strong>. With fewer than the minimum number of quotes (default 5) it shows
            <strong> INSUFFICIENT DATA</strong> and explains why. This is a rule you control. It is not a buy/wait forecast, and it cannot
            guarantee that the price will not fall later.
          </p>

          <h2>Why different flights are not directly comparable</h2>
          <p>
            Airline fares typically depend on how far ahead you book (lead time), the travel date and weekday, and holiday demand.
            A flight departing tomorrow is priced under different conditions than a New Year's Eve flight six weeks away, so their
            prices say little about each other without adjusting for lead time and travel date. That is why Compare Flights plots
            price against days-before-departure and flags weekdays and holidays, and why it is kept separate from the exact-flight
            history used for the status label.
          </p>

          <h2>What FareWatch cannot know</h2>
          <ul>
            <li>Remaining seats, fare-bucket inventory, passenger search volumes or the airline's internal demand.</li>
            <li>Whether a displayed fare is still available. Any fare must be re-checked on the official site.</li>
            <li>Baggage and add-on costs you have not recorded. Unknown fees are shown as unknown, not estimated.</li>
            <li>Whether a promotion applies to your flight. Promotions are logged, not assumed.</li>
          </ul>

          <h2>Collection limits</h2>
          <p>
            The optional collector checks the two target legs at most twice a day (Europe/Sarajevo time), stays within a daily cap
            (default 6 queries) and your monthly SerpApi quota, and skips a route checked within the minimum interval. Spare budget
            samples nearby November–January dates in rotation. Failed queries are logged; they never produce substitute prices.
            Google Flights may not list a Wizz Air flight or its price at all, which FareWatch reports as "not found" or "no price".
            SerpApi fares are stored with an assumed profile (basic fare, under-seat bag, taxes included, public), marked with *.
          </p>
        </div>

        <div className="space-y-6">
          <Card title="Experimental forecast evaluation">
            <ForecastPanel />
          </Card>
          <Card title="Before you buy">
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
              <li>Open the official Wizz Air site and search the exact date and flight number.</li>
              <li>Add the bags you actually need and compare the final total.</li>
              <li>Check whether a membership price is shown and whether you are eligible.</li>
              <li>FareWatch never books or pays automatically.</li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
