# FareWatch ✈️

**Find the cheapest flights from Sarajevo, and see whether today's price is actually a good deal.**

FareWatch started as a tool to find a cheap fare for a New Year's trip from Sarajevo to Rome. It's now a
small flight-deals site built on real observed fares, not invented predictions.

## Features

- **Explore from Sarajevo.** The homepage shows the cheapest destinations right now as deal cards (price,
  cheapest date, airline, nonstop or not). You can switch between one-way and round trip and filter by month.
  The data comes from Google Travel Explore via [SerpApi](https://serpapi.com/google-travel-explore-api).
- **Search any destination.** Type a city or airport and a date. A route page opens with the current fare, about
  60 days of Google Flights price history, a chart and a price status.
- **My trips.** Every route you search is saved. The original New Year in Rome trip has its own two-leg dashboard.
- **Real data only.** Fares come from Google Flights via [SerpApi](https://serpapi.com/google-flights-api), or
  from manual entries with a source link. Every price shows a badge with its source.
- **Analysis.** Min, max, median, 7-day median, volatility, drop detection, and days to departure, plus a
  simple status: *Attractive*, *Normal*, *Expensive* or *Insufficient data*. The status is a heuristic, not a
  forecast.
- **Only comparable fares are compared.** Baggage, taxes, passenger count and Discount Club member fares are
  kept separate.
- **Compare nearby dates.** Price is plotted against days before departure, with weekday and holiday flags.
- **Budget-safe.** Deals are cached and refresh at most every 6 hours. Daily and monthly search caps protect the
  free SerpApi plan (250 searches/month).
- **Honest by design.** Demo data is watermarked. Unknown baggage fees stay unknown. The app never books
  anything.

## Tech stack

**Frontend:** React · TypeScript · Vite · Tailwind CSS · Recharts
**Backend:** Python 3.12 · FastAPI · SQLAlchemy · Pydantic · SQLite (PostgreSQL-ready)
**Testing:** pytest (79 tests, no network calls)

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
