# PropEdge — Project Context

## Stack
- **Frontend**: Next.js 15 + React 18 + Tailwind CSS + SWR — deployed on **Vercel**
- **Backend**: FastAPI + async SQLAlchemy (asyncpg) + PostgreSQL + Redis — deployed on **Railway**
- **Workers**: Celery + Celery Beat (periodic tasks)
- **Auth**: JWT (`SECRET_KEY` env var) + Stripe subscription tiers
- **Branch**: `claude/ev-engine-line-shopping-a4wRC`

## Monorepo Layout
```
PropEdge/
├── frontend/          ← Next.js app (Vercel root directory = "frontend")
│   ├── src/app/       ← Pages: /, /login, /line-shop, /history, /analytics, /players, /pricing, /settings, /market, /props/[id]
│   ├── src/components/
│   │   ├── dashboard/ ← FiltersBar, PropsTable
│   │   ├── layout/    ← Sidebar (client component, usePathname)
│   │   └── shared/    ← EVBadge, ConfidenceMeter
│   ├── src/lib/
│   │   ├── api.ts     ← All API calls + SWR keys
│   │   ├── types.ts   ← All TypeScript types
│   │   └── utils.ts   ← cn, formatAmerican, formatPct, bookmakerLabel, etc.
│   ├── vercel.json    ← installCommand: npm install --legacy-peer-deps
│   └── .nvmrc         ← Node 20
└── backend/
    ├── app/
    │   ├── main.py
    │   ├── config.py  ← get_settings() — all env vars here
    │   ├── models/    ← Prop, Player, EVOpportunity, OddsSnapshot, etc.
    │   ├── routers/   ← props.py, analytics.py, auth.py, players.py
    │   ├── schemas/   ← Pydantic I/O schemas
    │   └── services/
    │       ├── ev_engine.py          ← EV + steam boost + line shopping
    │       ├── market/
    │       │   └── line_shopper.py   ← compute_line_shopping(), apply_line_shopping_to_prop()
    │       └── ingestion/
    │           ├── odds_collector.py ← The Odds API → snapshots + line shopping wired in
    │           └── sports_data.py    ← SportsDataIO game logs + defense rankings
    ├── alembic/versions/
    │   ├── 001_initial.py
    │   └── 002_line_shopping_steam.py
    ├── railway.toml   ← startCommand uses sh -c '... ${PORT:-8000}'
    └── nixpacks.toml
```

## Key Business Logic

### EV Formula
```
EV   = model_prob × decimal_odds − 1
Edge = model_prob − implied_prob
implied_prob = 1 / decimal_odds
```

### Tier Thresholds
| Tier     | EV      |
|----------|---------|
| standard | ≥ 3%    |
| high     | ≥ 8%    |
| elite    | ≥ 15%   |

### Ensemble Model Weights
| Component         | Weight |
|-------------------|--------|
| XGBoost           | 30%    |
| Sharp/Pinnacle    | 30%    |
| Bayesian          | 20%    |
| Distribution      | 20%    |

### Steam Detection
- ≥ 2 books move same direction, ≥ 0.5 pt delta, within 300s window
- Velocity = pts/min
- Confidence boost = `min(15, velocity × 5)`

### Line Shopping
- Sharp reference = Pinnacle
- Soft book = no-vig implied ≥ 2.5 pp below Pinnacle (`SOFT_THRESHOLD = 0.025`)
- Best over = highest decimal odds across soft books
- Line dispersion = std-dev of lines across soft books
- Runs automatically in `odds_collector._process_events()` after each batch

## Subscription Tiers
| Tier  | Price    | Prop limit | Features                            |
|-------|----------|------------|-------------------------------------|
| free  | $0       | 5          | Dashboard, basic EV                 |
| pro   | $49/mo   | Unlimited  | Steam, line shop, Discord webhook   |
| elite | $99/mo   | Unlimited  | Everything + SMS, priority alerts   |

## Environment Variables (backend)
```
DATABASE_URL            # PostgreSQL (auto from Railway)
REDIS_URL               # Redis (auto from Railway)
SECRET_KEY              # JWT signing key (openssl rand -hex 32)
ODDS_API_KEY            # The Odds API v4
SPORTS_DATA_API_KEY     # SportsDataIO v3 (optional)
STRIPE_SECRET_KEY       # Stripe
STRIPE_WEBHOOK_SECRET   # Stripe
ENVIRONMENT             # production
```

## Environment Variables (frontend / Vercel)
```
NEXT_PUBLIC_API_URL     # Backend Railway URL e.g. https://propedge.up.railway.app
```

## Deployment

### Frontend → Vercel
- Root Directory: `frontend`
- Branch: `claude/ev-engine-line-shopping-a4wRC`
- Install command in `vercel.json`: `npm install --legacy-peer-deps` (React 18 + legacy eslint peer deps)

### Backend → Railway
- Root Directory: `backend`
- Start command: `sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'`
- Add PostgreSQL + Redis as Railway services, link them (auto-sets DATABASE_URL / REDIS_URL)
- After first deploy run: `alembic upgrade head`

## API Endpoints (key ones)
```
GET  /props                  # List props (filters: sport, tier, direction, min_ev, min_confidence, best_available_only, has_steam)
GET  /props/top              # Top props
GET  /props/{id}             # Prop detail with live line shopping
GET  /props/line-shop        # Line shopping sorted by dispersion
GET  /props/steam            # Steam alerts
POST /props/{id}/result      # Resolve prop (set actual result + CLV)
GET  /analytics/performance  # Platform win rate / weekly stats
GET  /analytics/history      # Bet history with P&L, CLV (free tier capped at 25)
GET  /analytics/backtest     # Run backtest
GET  /players                # Player search
GET  /players/{id}           # Player detail + game logs
POST /auth/token             # Login → JWT
POST /auth/register          # Register
GET  /auth/me                # Current user
PATCH /auth/me               # Update alert prefs / discord webhook
POST /auth/checkout/{tier}   # Stripe checkout URL
GET  /health                 # Health check
```

## Known Issues / Notes
- React 18 (not 19) — `next@15.0.3` peer dep conflict with stable React 19; locked to React 18.3.1
- `useSearchParams` must be wrapped in `<Suspense>` on any page that uses it (Next.js 15 prerender requirement) — already fixed in `/settings`
- `sports_data.py` SportsDataIO integration is complete but requires `SPORTS_DATA_API_KEY`; no-ops gracefully without it
- CLV tracking is opt-in: pass `closing_line_odds_over` / `closing_line_odds_under` when resolving a prop
