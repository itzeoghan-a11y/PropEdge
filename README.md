# PropEdge

A data analysis engine for sports betting player props. PropEdge identifies positive expected-value (+EV) bets by comparing a multi-model probability estimate against live sportsbook lines, then surfaces the best available number across all books.

---

## What It Does

1. **Collects live odds** from The Odds API every 30 seconds across DraftKings, FanDuel, BetMGM, Caesars, and Pinnacle (as a sharp reference)
2. **Builds a true probability estimate** for each prop using an ensemble of four models: historical distribution fitting, Bayesian updating, XGBoost (optional), and the Pinnacle no-vig price
3. **Calculates EV** — `EV = model_prob × decimal_odds − 1` — and flags any bet where `edge ≥ 3%` and `confidence ≥ 50`
4. **Shops lines** across all books to find the best available number per direction and flag stale ("soft") lines that haven't caught up to sharp consensus
5. **Detects steam** — rapid coordinated line movement across 2+ books — and boosts confidence on matching EV opportunities
6. **Tracks results** — every flagged bet is stored with the odds at flag time and resolved against the actual result for backtesting and track-record display

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                  │
│  Dashboard · Market Intelligence · Prop Detail           │
└───────────────────┬─────────────────────────────────────┘
                    │ REST (SWR, 30s refresh)
┌───────────────────▼─────────────────────────────────────┐
│                   FastAPI Backend                         │
│  /props  /props/line-shop  /analytics/history            │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
┌──────▼──────┐                  ┌────────▼────────┐
│  PostgreSQL  │                  │     Redis        │
│  (asyncpg)  │                  │  (Celery broker) │
└──────────────┘                  └────────┬────────┘
                                           │
                          ┌────────────────▼───────────────┐
                          │        Celery Workers            │
                          │  collect_odds  (every 30s)       │
                          │  run_analysis  (every 2 min)     │
                          │  detect_steam  (every 60s)       │
                          │  send_alerts   (every 60s)       │
                          │  ingest_game_logs  (hourly)      │
                          │  train_ml_model    (3 AM UTC)    │
                          └────────────────────────────────┘
```

### Key Services

| Service | File | Purpose |
|---------|------|---------|
| EV Engine | `services/ev_engine.py` | Full analysis pipeline per prop |
| Line Shopper | `services/market/line_shopper.py` | Cross-book best available line |
| Steam Detector | `services/market/steam_detector.py` | Rapid line movement detection |
| Ensemble Model | `services/modeling/ensemble.py` | Multi-model probability estimate |
| Feature Engineer | `services/features/engineer.py` | Rolling stats, market features |
| Odds Collector | `services/ingestion/odds_collector.py` | The Odds API ingestion |
| Backtesting | `services/backtesting.py` | Historical P&L + Brier score |

### Probability Model

The ensemble combines four models:

| Model | Base Weight | Condition |
|-------|-------------|-----------|
| Sharp line (Pinnacle) | 30% | Always ≥ 25% when available |
| XGBoost (ML) | 30% | Requires ≥ 15 game samples + model file |
| Bayesian | 20% | Requires ≥ 5 historical games |
| Distribution fit | 20% | Requires ≥ 8 historical games |

Confidence score (0–100) adjusts for model agreement, sample size, data quality, and sharp-vs-soft deviation. Steam moves add up to +15 confidence points.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- The Odds API key (free tier works for testing)

### 1. Clone and configure

```bash
git clone <repo>
cd PropEdge
cp .env.example .env
# Edit .env — at minimum set ODDS_API_KEY and SECRET_KEY
```

### 2. Start the stack

```bash
docker compose up
```

This starts: PostgreSQL, Redis, FastAPI backend (port 8000), Celery worker, Celery beat scheduler, and Next.js frontend (port 3000).

### 3. Run the migration

```bash
docker compose exec backend alembic upgrade head
```

### 4. Open the dashboard

Visit [http://localhost:3000](http://localhost:3000).

The Celery beat scheduler will start collecting odds immediately. EV analysis runs every 2 minutes. It takes a few cycles before props appear.

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://user:pass@host/db`) |
| `REDIS_URL` | Redis connection string (`redis://host:6379/0`) |
| `SECRET_KEY` | JWT signing secret — generate with `openssl rand -hex 32` |
| `ODDS_API_KEY` | The Odds API v4 key — [the-odds-api.com](https://the-odds-api.com) |

### Optional — Data

| Variable | Default | Description |
|----------|---------|-------------|
| `SPORTS_DATA_API_KEY` | `` | Sportradar key for game logs + defense rankings |
| `ODDS_POLL_INTERVAL` | `30` | Seconds between odds refreshes |

### Optional — EV Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_EV_THRESHOLD` | `0.03` | Minimum edge to surface a bet (3%) |
| `MIN_CONFIDENCE_THRESHOLD` | `50` | Minimum model confidence (0–100) |
| `STEAM_DETECTION_WINDOW_SECONDS` | `300` | Window for steam move detection |

### Optional — Alerts

| Variable | Description |
|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Discord webhook for EV + steam alerts |
| `SENDGRID_API_KEY` | SendGrid key for email alerts |
| `TWILIO_ACCOUNT_SID` | Twilio account SID for SMS |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_FROM_NUMBER` | Twilio sending number |

### Optional — Payments

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_PRICE_PRO` | Stripe price ID for Pro tier |
| `STRIPE_PRICE_ELITE` | Stripe price ID for Elite tier |

### Optional — ML

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_ML_MODEL` | `false` | Enable XGBoost model in ensemble |

---

## API Reference

All endpoints require a JWT bearer token (`POST /auth/token` to obtain one).

### Props

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /props` | Any | Filtered list of +EV props |
| `GET /props/top` | Any | Top 10 highest-EV props |
| `GET /props/steam` | Pro+ | Recent steam alerts |
| `GET /props/line-shop` | Any | Props with book disagreement / soft lines |
| `GET /props/{id}` | Any | Full prop detail with line shopping breakdown |
| `POST /props/{id}/result` | Admin | Resolve prop with actual result |

**Key `GET /props` query params:**

| Param | Default | Description |
|-------|---------|-------------|
| `min_ev` | `0.03` | Minimum edge |
| `min_confidence` | `50` | Minimum confidence |
| `sport` | — | Filter by sport key |
| `tier` | — | `standard`, `high`, or `elite` |
| `best_available_only` | `false` | Only show best-available-line opportunities |
| `has_steam` | — | `true`/`false` to filter by steam presence |

### Analytics

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /analytics/performance` | Any | Platform-wide win rate + weekly stats |
| `GET /analytics/history` | Any | Full bet history with P&L per bet |
| `GET /analytics/backtest` | Pro+ | Run backtest over resolved bets |
| `GET /analytics/backtest/history` | Pro+ | Last 10 backtest runs |

### Auth

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create account |
| `POST /auth/token` | Login → JWT |
| `GET /auth/me` | Current user + tier |

---

## Line Shopping

PropEdge evaluates every available sportsbook simultaneously and:

- **Best available over** = book with the highest decimal odds for the over
- **Best available under** = book with the highest decimal odds for the under
- **Soft book** = a book whose no-vig implied probability is ≥ 2.5pp below Pinnacle's (they're behind the sharp line)
- **Line dispersion** = standard deviation of lines across all soft books — high dispersion means real shopping opportunity

The `GET /props/line-shop` endpoint returns props sorted by dispersion descending, filtered to those with at least one soft book. Use `min_dispersion` and `min_soft_books` to tune the filter.

---

## Steam Detection

A steam move is detected when:
- ≥ 2 books move in the same direction within a 5-minute window (`STEAM_DETECTION_WINDOW_SECONDS`)
- Total line delta ≥ 0.5 points
- Velocity ≥ 0.5 points/minute

When steam is detected, the EV engine applies a confidence boost to any matching EV opportunity:

```
boost = min(15, velocity × 5)
```

A fast steam move (3 pts/min) maxes out at +15 confidence. A slow move (0.6 pts/min) gives +3. The `steam_boosted` flag on the EVOpportunity records when this happened.

---

## Historical Tracking

Every flagged EV opportunity is stored with:
- The line and odds at time of flag (`line_at_flag`, `book_odds`)
- The model probability and confidence at flag time
- Whether it was the best available line (`is_best_available_line`)
- Whether steam boosted its confidence (`steam_boosted`)

Results are set via `POST /props/{id}/result` (admin only). Pass `closing_line_odds_over`/`closing_line_odds_under` to enable closing line value (CLV) tracking — positive CLV means you got better-than-closing odds.

The `/analytics/history` endpoint returns all resolved bets with per-bet P&L and a summary:

```json
{
  "bets": [{ "player_name": "...", "pnl": 0.91, "clv": 0.03, ... }],
  "summary": { "win_rate": 0.547, "roi": 0.068, "total_pnl": 14.2 }
}
```

---

## Subscription Tiers

| Feature | Free | Pro | Elite |
|---------|------|-----|-------|
| Dashboard props | 5/req | Unlimited | Unlimited |
| Bet history | 25 rows | Unlimited | Unlimited |
| Steam alerts | — | ✓ | ✓ |
| Backtesting | — | ✓ | ✓ |
| ML model output | — | — | ✓ (when enabled) |

---

## Development

```bash
# Backend only (with hot reload)
docker compose up backend redis db

# Run tests
docker compose exec backend pytest

# Apply new migrations
docker compose exec backend alembic upgrade head

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

---

## Project Structure

```
PropEdge/
├── backend/
│   ├── app/
│   │   ├── core/           auth.py (JWT)
│   │   ├── models/         SQLAlchemy ORM models
│   │   ├── routers/        FastAPI route handlers
│   │   ├── schemas/        Pydantic request/response models
│   │   ├── services/
│   │   │   ├── ev_engine.py            Core EV analysis
│   │   │   ├── backtesting.py
│   │   │   ├── alerts.py
│   │   │   ├── market/
│   │   │   │   ├── line_shopper.py     Cross-book best line
│   │   │   │   └── steam_detector.py  Steam move detection
│   │   │   ├── modeling/
│   │   │   │   ├── ensemble.py
│   │   │   │   ├── bayesian.py
│   │   │   │   ├── distribution.py
│   │   │   │   └── ml_model.py        XGBoost wrapper
│   │   │   ├── features/
│   │   │   │   └── engineer.py        Feature engineering
│   │   │   └── ingestion/
│   │   │       ├── odds_collector.py  The Odds API
│   │   │       └── sports_data.py     Game logs / defense rankings
│   │   └── workers/
│   │       └── tasks.py               Celery task definitions
│   └── alembic/
│       └── versions/
│           ├── 001_initial_schema.py
│           └── 002_line_shopping_steam.py
└── frontend/
    └── src/
        ├── app/            Next.js pages
        ├── components/     React components
        └── lib/            API client, types, utils
```
