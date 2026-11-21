# FareWatch ✈️

**A personal flight-price tracker that uses real observed fares, not invented predictions.**

I built FareWatch to find a cheap fare for a New Year's trip from **Sarajevo to Rome**
(Wizz Air W4 6160 on 31 Dec 2026, back on W4 6159 on 5 Jan 2027). It tracks prices over time, shows how today's
fare compares with recent history, and avoids comparing fares that differ in baggage or fees.

## Features

- **Real data only.** Fares come from manual entries (with a source link), CSV imports, or the optional
  [SerpApi](https://serpapi.com/google-flights-api) Google Flights API. Every price shows a badge with its source.
- **About 60 days of price history in one search.** Google Flights' recorded daily lowest prices are imported
  automatically.
- **Analysis.** Min, max, median, 7-day median, volatility, drop detection, and days to departure, plus a
  simple status: *Attractive*, *Normal*, *Expensive* or *Insufficient data*. The status is a heuristic, not a
  forecast.
- **Only comparable fares are compared.** Baggage, taxes, passenger count and Discount Club member fares are
  kept separate.
- **Compare nearby dates.** Price is plotted against days before departure, with weekday and holiday flags.
- **Alerts.** Price-threshold and percentage-drop alerts, with de-duplication.
- **Budget-safe automation.** An opt-in scheduler (Europe/Sarajevo time) with daily and monthly query caps.
- **Honest by design.** Demo data is watermarked. Unknown baggage fees stay unknown. The app never books
  anything.

## Tech stack

**Frontend:** React · TypeScript · Vite · Tailwind CSS · Recharts
**Backend:** Python 3.12 · FastAPI · SQLAlchemy · Pydantic · SQLite (PostgreSQL-ready)
**Testing:** pytest (69 tests, no network calls)

## Quick start

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cd .. && cp .env.example .env
cd backend && uvicorn app.main:app --port 8000

# Frontend (in a second terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**. The app works without an API key. To fetch prices automatically, add a free
SerpApi key to `.env`.

Windows commands, scheduling, tests and deployment notes are in **[docs/SETUP.md](docs/SETUP.md)**.

## Disclaimer

FareWatch is a personal project. Prices are past observations and can change at any time. Always verify the
final price, including baggage and fees, on the airline's official site. It is not affiliated with Wizz Air,
Google or SerpApi.
