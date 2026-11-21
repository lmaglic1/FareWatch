import type { ReactNode } from "react";
import type { Status } from "../lib/api";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, action, children, className = "" }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, badge }: { label: string; value: ReactNode; hint?: ReactNode; badge?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs font-medium text-ink-3">{label}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-2">
        <span className="text-xl font-semibold tabular-nums text-ink">{value}</span>
        {badge}
      </div>
      {hint && <div className="mt-0.5 text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

const SOURCE_META: Record<string, { label: string; cls: string; title: string }> = {
  manual: { label: "Manual", cls: "bg-accent-soft text-accent-ink", title: "Entered by you from a page you viewed" },
  serpapi_google_flights: {
    label: "Google Flights · SerpApi",
    cls: "bg-good-soft text-good",
    title: "Returned by SerpApi's Google Flights API; not re-verified on the airline site",
  },
  serpapi_price_history: {
    label: "Google price history",
    cls: "bg-good-soft text-good",
    title: "Google Flights' recorded lowest price for this search on that day (via SerpApi)",
  },
  csv_import: { label: "CSV import", cls: "bg-raised text-ink-2 ring-1 ring-hair", title: "Imported from a CSV file (unverified)" },
  demo_fixture: { label: "DEMO", cls: "bg-warn-soft text-warn", title: "Synthetic demo fixture: not a real price" },
};

export function SourceBadge({ source, assumed }: { source: string; assumed?: boolean }) {
  const m = SOURCE_META[source] ?? { label: source, cls: "bg-raised text-ink-2", title: source };
  return (
    <span
      title={m.title + (assumed ? ". Fare/baggage profile assumed." : "")}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-medium ${m.cls}`}
    >
      {m.label}
      {assumed && <span aria-label="profile assumed">*</span>}
    </span>
  );
}

export function MemberBadge() {
  return (
    <span title="Wizz Discount Club member fare - requires a paid membership; not generally available"
      className="inline-flex rounded-md bg-warn-soft px-1.5 py-0.5 text-[11px] font-medium text-warn">
      Member fare
    </span>
  );
}

const STATUS_META: Record<Status, { cls: string; icon: string }> = {
  "INSUFFICIENT DATA": { cls: "bg-raised text-ink-2 ring-1 ring-hair", icon: "○" },
  "ATTRACTIVE PRICE": { cls: "bg-good-soft text-good", icon: "↓" },
  "NORMAL RANGE": { cls: "bg-accent-soft text-accent-ink", icon: "≈" },
  "EXPENSIVE RELATIVE TO HISTORY": { cls: "bg-bad-soft text-bad", icon: "↑" },
};

export function StatusPill({ status }: { status: Status }) {
  const m = STATUS_META[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide ${m.cls}`}>
      <span aria-hidden>{m.icon}</span>
      {status}
    </span>
  );
}

export function DemoWatermark({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <>
      <div className="mb-5 rounded-lg border border-dashed border-warn bg-warn-soft px-4 py-2.5 text-sm text-warn" role="status">
        <strong>Demo mode.</strong> Everything below is synthetic fixture data, not real prices. Turn demo mode off in
        Settings to see your real observations.
      </div>
      <div aria-hidden className="pointer-events-none fixed inset-0 z-0 flex items-center justify-center overflow-hidden">
        <span className="-rotate-[24deg] select-none text-[18vw] font-black tracking-widest text-warn opacity-[0.06]">
          DEMO
        </span>
      </div>
    </>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm text-ink-3" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-hair border-t-accent" />
      {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-hair bg-bad-soft px-4 py-3 text-sm text-bad sm:flex-row sm:items-center sm:justify-between" role="alert">
      <span>{message}</span>
      {onRetry && <button className="btn-ghost" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-hair px-5 py-8 text-center">
      <div className="text-sm font-medium text-ink">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-ink-3">{children}</div>}
    </div>
  );
}

export function Notice({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warn" }) {
  const cls = tone === "warn" ? "bg-warn-soft text-warn" : "bg-raised text-ink-2 ring-1 ring-hair";
  return <div className={`rounded-lg px-4 py-3 text-xs leading-relaxed ${cls}`}>{children}</div>;
}

export function Toast({ message, tone, onClose }: { message: string; tone: "good" | "bad"; onClose: () => void }) {
  return (
    <div className={`flex items-start justify-between gap-3 rounded-lg px-4 py-3 text-sm ${tone === "good" ? "bg-good-soft text-good" : "bg-bad-soft text-bad"}`} role="status">
      <span>{message}</span>
      <button onClick={onClose} aria-label="Dismiss" className="text-current opacity-70 hover:opacity-100">✕</button>
    </div>
  );
}
