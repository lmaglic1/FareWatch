import { useState, type FormEvent } from "react";
import { api, ApiError, type Flight } from "../lib/api";
import { dateLong } from "../lib/format";
import { Toast } from "./ui";

function nowLocalInput(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

const CURRENCIES = ["EUR", "BAM", "USD", "GBP", "CHF", "HUF", "RSD", "PLN"];

export function ManualEntryForm({ flights, defaultFlightId, displayCurrency, onSaved }: {
  flights: Flight[];
  defaultFlightId?: number;
  displayCurrency: string;
  onSaved: () => void;
}) {
  const [flightId, setFlightId] = useState<number>(defaultFlightId ?? flights[0]?.id ?? 0);
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState(displayCurrency);
  const [capturedAt, setCapturedAt] = useState(nowLocalInput());
  const [passengers, setPassengers] = useState(1);
  const [fareProduct, setFareProduct] = useState("basic");
  const [baggage, setBaggage] = useState("under_seat_only");
  const [taxes, setTaxes] = useState("yes");
  const [club, setClub] = useState("public");
  const [sourceUrl, setSourceUrl] = useState("");
  const [fxRate, setFxRate] = useState("");
  const [fxSource, setFxSource] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ msg: string; tone: "good" | "bad" } | null>(null);

  const needsFx = currency !== displayCurrency && !(currency === "BAM" && displayCurrency === "EUR");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setToast(null);
    try {
      const res = await api.addObservation({
        flight_id: flightId,
        price_total: price.trim().replace(",", "."),
        currency,
        captured_at_utc: new Date(capturedAt).toISOString(),
        passengers,
        fare_product: fareProduct,
        baggage_profile: baggage,
        taxes_fees_included: taxes,
        discount_club: club,
        source_url: sourceUrl.trim() || null,
        fx_rate_to_display: needsFx && fxRate ? fxRate : null,
        fx_source: needsFx && fxSource ? fxSource : null,
        notes: notes.trim() || null,
      });
      setToast({
        msg: res.duplicate
          ? res.message
          : `Saved.${res.alerts_triggered ? ` ${res.alerts_triggered} alert(s) triggered.` : ""}`,
        tone: res.duplicate ? "bad" : "good",
      });
      if (!res.duplicate) {
        setPrice("");
        setNotes("");
        onSaved();
      }
    } catch (err) {
      const e2 = err as ApiError;
      const detail = e2.details?.length ? e2.details.map((d) => `${d.field}: ${d.message}`).join("; ") : e2.message;
      setToast({ msg: detail, tone: "bad" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-xs text-ink-3">
        Record a fare you personally saw on an official booking or search page. Enter the <strong>total</strong> for all
        passengers, exactly as shown.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="sm:col-span-2">
          <span className="field-label">Flight</span>
          <select className="input" value={flightId} onChange={(e) => setFlightId(Number(e.target.value))}>
            {flights.map((f) => (
              <option key={f.id} value={f.id}>
                {f.flight_number} · {f.origin}→{f.destination} · {dateLong(f.flight_date)}
                {f.is_target ? " (target)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Total price</span>
          <input className="input tabular-nums" inputMode="decimal" required placeholder="e.g. 64.99" value={price}
            onChange={(e) => setPrice(e.target.value)} pattern="^\d{1,5}([.,]\d{1,2})?$"
            title="Amount with up to 2 decimals" />
        </label>
        <label>
          <span className="field-label">Currency</span>
          <select className="input" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        {needsFx && (
          <>
            <label>
              <span className="field-label">Rate: 1 {currency} = ? {displayCurrency}</span>
              <input className="input" required inputMode="decimal" value={fxRate} onChange={(e) => setFxRate(e.target.value)} />
            </label>
            <label>
              <span className="field-label">Rate source</span>
              <input className="input" required placeholder="e.g. ECB reference rate 2026-11-21" value={fxSource}
                onChange={(e) => setFxSource(e.target.value)} />
            </label>
          </>
        )}
        <label>
          <span className="field-label">Seen at (your local time)</span>
          <input className="input" type="datetime-local" required value={capturedAt} onChange={(e) => setCapturedAt(e.target.value)} />
        </label>
        <label>
          <span className="field-label">Passengers</span>
          <input className="input" type="number" min={1} max={9} value={passengers} onChange={(e) => setPassengers(Number(e.target.value))} />
        </label>
        <label>
          <span className="field-label">Fare product</span>
          <select className="input" value={fareProduct} onChange={(e) => setFareProduct(e.target.value)}>
            <option value="basic">Basic</option>
            <option value="wizz_go">Wizz GO</option>
            <option value="wizz_plus">Wizz PLUS</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label>
          <span className="field-label">Baggage included in this price</span>
          <select className="input" value={baggage} onChange={(e) => setBaggage(e.target.value)}>
            <option value="under_seat_only">Free under-seat bag only</option>
            <option value="priority_trolley">Priority + cabin trolley</option>
            <option value="checked_bag">Checked bag</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label>
          <span className="field-label">Taxes & fees included?</span>
          <select className="input" value={taxes} onChange={(e) => setTaxes(e.target.value)}>
            <option value="yes">Yes</option>
            <option value="no">No</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label>
          <span className="field-label">Wizz Discount Club</span>
          <select className="input" value={club} onChange={(e) => setClub(e.target.value)}>
            <option value="public">Public fare (no membership)</option>
            <option value="member">Member fare</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <label className="sm:col-span-2">
          <span className="field-label">Source URL (page where you saw it)</span>
          <input className="input" type="url" placeholder="https://wizzair.com/..." value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
        </label>
        <label className="sm:col-span-2">
          <span className="field-label">Notes (optional)</span>
          <input className="input" maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>
      {toast && <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} />}
      <button className="btn-primary w-full sm:w-auto" disabled={busy || !flights.length}>
        {busy ? "Saving…" : "Save observation"}
      </button>
    </form>
  );
}
