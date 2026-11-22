import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { exploreApi, type Airport } from "../lib/api";

function tomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

/** From (home airport) -> To (any airport) on a date. Opens the route page and runs a search. */
export function SearchBar({ origin = "SJJ", originLabel = "Sarajevo" }: { origin?: string; originLabel?: string }) {
  const nav = useNavigate();
  const [query, setQuery] = useState("");
  const [dest, setDest] = useState<Airport | null>(null);
  const [options, setOptions] = useState<Airport[]>([]);
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState(tomorrow());
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number>();

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (dest || query.trim().length < 2) {
      setOptions([]);
      return;
    }
    timer.current = window.setTimeout(() => {
      exploreApi.airports(query).then((r) => { setOptions(r.filter((a) => a.code !== origin)); setOpen(true); }).catch(() => setOptions([]));
    }, 200);
  }, [query, dest, origin]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const code = dest?.code ?? (query.trim().length === 3 ? query.trim().toUpperCase() : null);
    if (!code) return setError("Choose a destination from the list or type a 3-letter airport code.");
    setError(null);
    nav(`/route/${origin}/${code}/${date}`, { state: { search: true } });
  }

  return (
    <form onSubmit={submit} className="rounded-2xl bg-surface p-2 shadow-card">
      <div className="grid gap-2 sm:grid-cols-[1fr_1.4fr_1fr_auto]">
        <div className="rounded-xl px-3 py-2 ring-1 ring-hair">
          <div className="text-[11px] font-medium text-ink-3">From</div>
          <div className="truncate text-sm font-medium text-ink">{originLabel} <span className="text-ink-3">{origin}</span></div>
        </div>
        <div className="relative rounded-xl px-3 py-2 ring-1 ring-hair focus-within:ring-accent">
          <label htmlFor="dest" className="text-[11px] font-medium text-ink-3">To</label>
          <input
            id="dest" autoComplete="off" placeholder="City or airport, e.g. Rome"
            className="block w-full bg-transparent text-sm font-medium text-ink placeholder:font-normal placeholder:text-ink-3 focus:outline-none"
            value={dest ? `${dest.city} (${dest.code})` : query}
            onChange={(e) => { setDest(null); setQuery(e.target.value); }}
            onFocus={() => options.length && setOpen(true)}
            onBlur={() => window.setTimeout(() => setOpen(false), 150)}
            role="combobox" aria-expanded={open} aria-controls="dest-list"
          />
          {open && options.length > 0 && (
            <ul id="dest-list" role="listbox" className="absolute left-0 right-0 top-full z-40 mt-1 max-h-72 overflow-auto rounded-xl bg-raised py-1 shadow-card">
              {options.map((a) => (
                <li key={a.code}>
                  <button type="button" role="option" aria-selected={false}
                    className="flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-accent-soft"
                    onMouseDown={() => { setDest(a); setOpen(false); }}>
                    <span className="truncate"><span className="font-medium text-ink">{a.city}</span> <span className="text-ink-3">{a.name}</span></span>
                    <span className="shrink-0 text-xs font-semibold text-ink-2">{a.code} · {a.country}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl px-3 py-2 ring-1 ring-hair focus-within:ring-accent">
          <label htmlFor="date" className="text-[11px] font-medium text-ink-3">Date (one way)</label>
          <input id="date" type="date" min={tomorrow()} value={date} onChange={(e) => setDate(e.target.value)}
            className="block w-full bg-transparent text-sm font-medium text-ink focus:outline-none" />
        </div>
        <button className="btn-primary rounded-xl px-6 text-base">Search</button>
      </div>
      {error && <p className="px-3 pb-1 pt-2 text-xs text-bad">{error}</p>}
    </form>
  );
}
