# FareWatch

FareWatch is a personal flight-price tracker built on **real recorded observations**. It was built to find the
cheapest reasonable fares for a New Year's trip from Sarajevo to Rome, and it works for any airports you add.

| Leg | Date | Flight | Scheduled (local) |
|---|---|---|---|
| Outbound SJJ → FCO | Thu 31 Dec 2026 | Wizz Air Malta W4 6160 | 21:10 Sarajevo → 22:35 Rome |
| Return FCO → SJJ | Tue 5 Jan 2027 | Wizz Air Malta W4 6159 | 15:05 Rome → 16:35 Sarajevo |

These schedules are preliminary. They are not confirmed live availability. When a provider returns the flight,
FareWatch records whether the times match. The defaults are 1 adult, economy, direct flights, and EUR.

> FareWatch never books or pays. It doesn't promise you the lowest price. Prices shown are past observations,
> so always check the final price, including baggage and fees, on the airline's official site.

---

## What it does

- **Manual entry**: record a fare you saw, with the page URL and the time you saw it.
- **CSV import/export**: import historical observations (each row is validated) and export your real data.
- **SerpApi Google Flights (optional)**: an automated real-data source. It searches each leg as a one-way
  nonstop trip and matches the exact flight number, date, route and stop count. If the flight is missing or
  has no price, FareWatch logs that and stores no price.
- **Dashboard**: shows the last observed quote, the best recorded quote, the median, the 7-day median, days
  until departure, data freshness and a status label.
- **Flight Details**: separate charts for the outbound and return legs, with timestamps and sources.
- **Compare Flights**: nearby departures from November 2026 to January 2027, plotted as price versus days
  before departure, with weekday and holiday indicators.
- **Price History**: every observation, with filters, sorting, CSV import and CSV export.
- **Alerts**: price-threshold and percentage-drop rules, with de-duplication and an alert history.
  Email alerts are optional.
- **Bags & Promotions**: fare-plus-baggage comparisons using fees you recorded (unknown fees stay unknown),
  the Discount Club membership cost shown separately, and a promotions log.
- **Settings**: provider connection status, currency, baggage profile, refresh cadence, API budget,
  demo mode and a collection log.
- **About the Algorithm**: the assumptions, the limits, and a gated experimental forecast evaluation.

Every price carries a **source badge**. Demo fixtures appear only in demo mode, always under a **DEMO
watermark**, and are never mixed into real analysis, alerts or exports.

---

## Repository layout

```
FareWatch/
├── backend/                 FastAPI + SQLAlchemy (Python 3.12+)
│   ├── app/
│   │   ├── main.py          API entry point (CORS, error handling, startup)
│   │   ├── config.py        settings from .env
│   │   ├── models.py        database tables
│   │   ├── money.py         Decimal / minor-unit money handling and FX provenance
│   │   ├── flights.py       flight identities, airports/timezones, target seed
│   │   ├── scheduler.py     opt-in scheduled collector (APScheduler)
│   │   ├── providers/       manual, csv_import, serpapi_google_flights
│   │   ├── services/        analysis, alerts, collector, quota, features, forecast, demo
│   │   └── routers/         HTTP endpoints
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/                React + TypeScript + Vite + Tailwind + Recharts
│   └── src/pages/           Dashboard, FlightDetails, Compare, History, Alerts, Extras, Settings, About
├── tests/                   pytest suite (+ a clearly labelled TEST FIXTURE JSON)
├── .env.example             configuration template (no secrets)
├── pytest.ini
└── README.md
```

---

## 1. Install the prerequisites (once)

- **Python 3.12 or newer**: https://www.python.org/downloads/ (on Windows, tick "Add python.exe to PATH").
- **Node.js 20 LTS or newer**: https://nodejs.org/
- **Git**: https://git-scm.com/

Check them:

```bash
python3 --version   # macOS/Linux: needs 3.12+   (Windows: py -3.12 --version)
node --version      # v20+
```

## 2. Set up the backend

**macOS / Linux**

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cd ..
cp .env.example .env
```

**Windows PowerShell**

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cd ..
Copy-Item .env.example .env
```

> If PowerShell refuses to run `Activate.ps1`, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

## 3. Run the backend

Open a terminal and keep it running.

**macOS / Linux**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Windows PowerShell**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

The API runs at http://127.0.0.1:8000, and interactive API docs are at http://127.0.0.1:8000/docs.
The SQLite database is created automatically at `backend/data/farewatch.db`.

## 4. Run the frontend

Open a **second** terminal:

```bash
cd frontend
npm install
npm run dev
```

(The same commands work in PowerShell.)

## 5. Open the app

Go to **http://localhost:5173**. The frontend forwards `/api` requests to the backend on port 8000.

To record your first fare, open the Dashboard and use **Record a fare you saw**. Enter the total price exactly
as shown on the booking page, the baggage that price includes, and whether it is a Discount Club member fare.

To explore with sample data, turn on **Settings → Demo mode**. Turning it off deletes the demo data.

---

## 6. Add a SerpApi key later (optional)

1. Create an account at https://serpapi.com/ and copy your private API key.
2. Open `.env` in the repository root and set `SERPAPI_API_KEY=your_key_here`.
3. Set `SERPAPI_MONTHLY_QUOTA` to your plan's monthly search allowance.
4. Restart the backend (stop it with `Ctrl+C`, then run the uvicorn command again).
5. In Settings, "SerpApi Google Flights" should now show **Connected**. "Check SerpApi account usage" calls the
   free Account API, which does not use up any searches.
6. On the Dashboard, click **Refresh prices now** to run one manual check.

How the SerpApi data is handled:

- Each leg is a separate one-way query (`engine=google_flights`, `type=2`, `stops=1`, `travel_class=1`).
- A result counts as your flight only if it matches the flight number (e.g. `W4 6160` → `W46160`), the local
  departure date, the route, and has zero stops.
- Google Flights may not list a Wizz Air flight or its price. That is logged as `not_found` or `no_price`
  and no observation is stored.
- Google Flights fares are stored with an **assumed** profile: basic fare, under-seat bag only, taxes
  included, public fare. They are marked with `*`. Check them on the airline's site.
- Other nonstop flights in the same results are stored as comparison flights, each with its own identity.

### Importing past prices (Google price history)

Every SerpApi Google Flights search also returns `price_insights.price_history`: Google's recorded
**lowest price for that exact search on each of roughly the last 60 days**. FareWatch stores these points
automatically with the source badge **Google price history**. So your first **Refresh prices now** (2 searches)
fills about two months of history for both legs. **Settings → Import Google price history** does the same for
the target legs plus up to N nearby November–January dates, within the daily cap.

- History is the lowest nonstop price for the search, not for a named flight. FareWatch attributes it to a
  flight only when that flight is the **only** nonstop flight in the results, which is true for SJJ ⇄ FCO
  (Wizz Air only). Otherwise the history is skipped and the reason is logged.
- History points are in whole euros, use the same assumed fare profile as other SerpApi data, and never
  trigger alerts.
- Prices of flights that have **already departed** (e.g. last year's New Year flights) are not available
  from any free source. Only paid enterprise datasets (e.g. OAG) sell them.

## 7. Configure scheduled checks (optional)

In `.env`:

```ini
COLLECTOR_ENABLED=true
COLLECTOR_TIMES=08:00,20:00        # Europe/Sarajevo local time
MAX_QUERIES_PER_DAY=6              # hard daily cap (Sarajevo calendar day)
MIN_MINUTES_BETWEEN_CHECKS=120     # never re-check a route/date sooner than this
COLLECTOR_INCLUDE_COMPARISONS=true # spare budget samples nearby Nov–Jan dates
```

Then restart the backend. By default the budget works out like this: 2 runs × 2 target legs = 4 queries,
which leaves 2 for comparison samples. Manual refreshes count toward the same cap. The monthly quota is also
enforced. Every attempt (success, failure or skip) appears in **Settings → Collection log**. A failed query
never produces a substitute price. Timestamps are stored in UTC, and the schedule follows Europe/Sarajevo time.

> **The local scheduler only runs while the backend is running.** If your computer is asleep or the server is
> stopped at 08:00, that check is skipped, not caught up later.

### Running it in the cloud (future)

For checks that run without your laptop:

1. Use **persistent external storage**: a managed PostgreSQL database (for example Neon, Supabase, or AWS RDS).
   Set `DATABASE_URL=postgresql+psycopg://...` and install a driver (`pip install "psycopg[binary]"`).
   Don't rely on a container's local disk for SQLite, because it can be wiped on redeploy.
2. Deploy the backend as a small always-on service (Render, Fly.io, Railway, or a VPS), with secrets set as
   environment variables in the host's dashboard. Never put them in Git.
3. Better still, set `COLLECTOR_ENABLED=false` on the web service and trigger `POST /api/collector/run` from
   the platform's cron job. The quota and minimum-interval rules still apply.
4. Build the frontend with `npm run build` and serve `frontend/dist` from a static host, with `/api` routed
   to the backend. Restrict `CORS_ORIGINS` to your real domain.
5. Put authentication in front of it (for example the platform's access control). FareWatch has no user
   accounts.

## 8. Run the tests

From the repository root:

**macOS / Linux**

```bash
backend/.venv/bin/python -m pytest
```

**Windows PowerShell**

```powershell
backend\.venv\Scripts\python -m pytest
```

The tests use a temporary database and make **no network calls**. SerpApi is simulated with
`httpx.MockTransport` and a fixture file named `*_TEST_FIXTURE.json`. They cover price storage, duplicate
handling, flight matching, API response parsing, missing-price and error conditions, statistics, alerts,
quota caps, CSV validation and the HTTP API.

Frontend type check and production build:

```bash
cd frontend
npm run build
```

## 9. Use Git safely

- `.env` is in `.gitignore`. **Never commit API keys or SMTP passwords.** Before every commit, check what is
  staged:
  ```bash
  git status
  git diff --staged
  ```
- Your observations live in `backend/data/` (also ignored). Back them up by exporting a CSV
  (Price History → Export CSV) and storing it somewhere private.
- Typical workflow:
  ```bash
  git checkout -b my-change        # work on a branch
  git add -A
  git status                       # confirm no .env / .db files are listed
  git commit -m "Describe the change"
  git push -u origin my-change
  ```
- If a secret is ever committed, **revoke it at the provider immediately** (generate a new SerpApi key).
  Deleting the commit is not enough once it has been pushed.

---

## CSV format

Required columns: `flight_number, origin, destination, flight_date, captured_at_utc, price_total, currency`.
Optional columns: `passengers, fare_product (basic|wizz_go|wizz_plus|unknown), baggage_profile
(under_seat_only|priority_trolley|checked_bag|unknown), taxes_fees_included (yes|no|unknown), discount_club
(public|member|unknown), airline, scheduled_departure_local, scheduled_arrival_local, source_url,
booking_url, notes`.

```csv
flight_number,origin,destination,flight_date,captured_at_utc,price_total,currency,baggage_profile,discount_club,source_url
W4 6160,SJJ,FCO,2026-12-31,2026-11-20T08:15:00Z,64.99,EUR,under_seat_only,public,https://wizzair.com/
```

`captured_at_utc` must include a timezone. Invalid rows are reported by row number and skipped. Exact
duplicates are skipped. Demo rows are rejected. Imported rows are labelled `imported_unverified`. Use
"Validate only" for a dry run.

## Money and currencies

Prices are stored as integer minor units (cents) and handled as `Decimal`, never as floats, and the API returns
them as decimal strings. The original currency and amount are always kept. BAM converts to EUR at the fixed
currency-board peg (1 EUR = 1.95583 BAM), which is recorded as the rate's source. Any other conversion needs a
rate **and** a source that you provide.

## How the analysis works (summary)

- Quotes are compared only when currency, passengers, fare product, baggage, taxes and Discount Club status
  all match.
- Statistics: min, max, median, average, count, change versus the previous quote, 7-day median (needs at least
  3 quotes in the last 7 days), rank, volatility (SD and coefficient of variation), drop detection, days to
  departure, and the time of the last valid quote.
- Status: **INSUFFICIENT DATA** until at least 5 comparable quotes exist (configurable). After that, the latest
  quote is compared with the median of the earlier ones, using your threshold (default ±15%), to give
  **ATTRACTIVE PRICE**, **NORMAL RANGE** or **EXPENSIVE RELATIVE TO HISTORY**. This is a heuristic you
  control, not a forecast.
- Exact-flight history is kept separate from the cross-flight lead-time view. A flight leaving tomorrow and a
  holiday flight six weeks away are priced under different conditions, so the Compare page groups prices by
  days before departure and flags weekdays and holidays.
- The experimental forecast evaluation stays disabled until there are at least 40 genuine comparable
  observations, spanning 21 days or more, across at least 2 flights. It then uses a chronological 80/20 split
  and reports MAE against a last-price baseline, plus an error band.

## Adding other airports

Add the airport and its IANA timezone to `AIRPORTS` in `backend/app/flights.py`. Then create flights in
**Compare Flights → Add a comparison flight**, or through `POST /api/flights`.
