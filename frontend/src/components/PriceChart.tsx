import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Observation } from "../lib/api";
import { money, timestamp, timestampUtc } from "../lib/format";

interface Point {
  t: number;
  price: number;
  obs: Observation;
}

const SOURCE_NAME: Record<string, string> = {
  manual: "Manual",
  serpapi_google_flights: "Google Flights (SerpApi)",
  serpapi_price_history: "Google price history (SerpApi)",
  csv_import: "CSV import",
  demo_fixture: "DEMO fixture",
};

function TooltipBody({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const o = payload[0].payload.obs;
  return (
    <div className="rounded-lg bg-raised px-3 py-2 text-xs shadow-card">
      <div className="text-sm font-semibold tabular-nums text-ink">{money(o.price_total, o.currency)}</div>
      <div className="mt-0.5 text-ink-2">{timestamp(o.captured_at_utc)} · {timestampUtc(o.captured_at_utc)}</div>
      <div className="text-ink-3">
        {SOURCE_NAME[o.source] ?? o.source} · {o.lead_time_days} days before departure
      </div>
    </div>
  );
}

/** Single-series price line for one flight + one comparable fare profile. */
export function PriceChart({ observations, median, height = 260 }: {
  observations: Observation[];
  median?: string | null;
  height?: number;
}) {
  const data: Point[] = observations
    .map((o) => ({ t: new Date(o.captured_at_utc).getTime(), price: Number(o.price_total), obs: o }))
    .sort((a, b) => a.t - b.t);
  const currency = observations[0]?.currency ?? "EUR";
  const prices = data.map((d) => d.price);
  const lo = Math.min(...prices);
  const hi = Math.max(...prices);
  const pad = Math.max(5, (hi - lo) * 0.15);

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" strokeWidth={1} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(t) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--axis)" }}
            tickLine={false}
            minTickGap={32}
          />
          <YAxis
            domain={[Math.floor(lo - pad), Math.ceil(hi + pad)]}
            tickFormatter={(v) => money(String(v), currency).replace(/\.00$/, "")}
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={64}
          />
          {median && (
            <ReferenceLine
              y={Number(median)}
              stroke="var(--chart-muted)"
              strokeDasharray="4 4"
              label={{ value: `median ${money(median, currency)}`, position: "insideTopRight", fill: "var(--chart-muted)", fontSize: 11 }}
            />
          )}
          <Tooltip content={<TooltipBody />} cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} />
          <Line
            type="monotone"
            dataKey="price"
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={data.length <= 40 ? { r: 3.5, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 } : false}
            activeDot={{ r: 5, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
