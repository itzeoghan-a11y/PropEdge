# PropEdge — Context for Claude

Player-prop analytics platform. Monorepo: FastAPI backend + Next.js frontend, deployed to Railway (backend + Postgres + Redis) and Vercel/Railway (frontend).

## Layout

```
backend/           FastAPI + SQLAlchemy async + Celery
  app/
    main.py        ASGI entry; registers routers, /health, startup hook
    config.py      Pydantic settings; env var aliases
    database.py    Async engine, AsyncSessionLocal, create_tables()
    core/auth.py   JWT-ish token utils, get_current_user, require_pro
    models/        SQLAlchemy ORM (User, Player, Prop, Odds, EVOpportunity, SteamAlert, …)
    routers/       auth, props, players, analytics
    services/
      ev_engine.py        EV calc + tier classification
      backtesting.py      run_backtest()
      alerts.py           Discord / SendGrid / Twilio fan-out
      ingestion/          Odds API + sports-data pollers
      market/             steam detection, sharp/soft consensus
      modeling/ml_model.py  XGBoost + isotonic calibration (joblib in MODEL_CACHE_DIR)
      features/engineer.py  PropFeatures → 19-dim feature vector
    workers/tasks.py      Celery beat tasks
  alembic/        migrations (production schema source of truth)
  Dockerfile, nixpacks.toml, railway.toml
frontend/         Next.js 14 (app router) + Tailwind; Dockerfile + railway.toml
docker-compose.yml  local dev (postgres + redis + backend + frontend)
.env.example      authoritative env var list
```

## Stack pins worth remembering

- Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (async), asyncpg, Pydantic v2.
- numpy 2.1, scipy 1.14, xgboost 2.1, scikit-learn 1.5 — these need gcc + Python ≥3.10 wheels.
- Celery 5.4 with Redis broker.

## Key business logic (don't reinvent)

- **EV formula** in `services/ev_engine.py`: `EV = p_true*payout - (1-p_true)*stake`. Probability blends ML model + sharp consensus; soft books are the EV target.
- **Tiers**: based on `min_ev_threshold` (default 0.03) and `min_confidence_threshold` (50). Configurable via env.
- **Steam detection** in `services/market/`: line moves across N sharp books inside `STEAM_DETECTION_WINDOW_SECONDS` (default 300).
- **Sharp books**: pinnacle, betfair, matchbook. **Soft books**: draftkings, fanduel, betmgm, caesars, pointsbetus. Hardcoded in `config.py`.
- **ML feature order** (19 features) is fixed in `services/modeling/ml_model.py:FEATURE_NAMES` — must match training set order.

## Env vars (see `.env.example` for the full list)

Required to boot: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`.
Required for full functionality: `ODDS_API_KEY`, `SPORTS_DATA_API_KEY`, `STRIPE_*`.
Optional: alert channels (`DISCORD_WEBHOOK_URL`, `SENDGRID_API_KEY`, `TWILIO_*`).

`config.py` accepts `postgres://` / `postgresql://` / `postgresql+asyncpg://` and normalises to asyncpg.

## API surface

- `GET  /health` — Railway healthcheck. Trivial; no DB.
- `POST /auth/register`, `/auth/login`, `/auth/stripe/webhook`
- `GET  /props/...` — list, filter by sport/tier/EV
- `GET  /players/...`
- `GET  /analytics/...` — backtests, performance (Pro tier gated)

## Deployment

### Railway (backend)
- Service root: **must be set to `backend/`** so `railway.toml` is picked up.
- Builder: `railway.toml` says `nixpacks`, but Railway auto-detects the Dockerfile when present. Both paths are now wired (Dockerfile has CMD, nixpacks pins python312).
- Healthcheck: `GET /health`, timeout `300s` (cold-boot headroom for ML model load).
- Provision Postgres + Redis plugins; their connection strings inject as `DATABASE_URL` / `REDIS_URL` automatically.
- Run `alembic upgrade head` as a release/deploy command — production startup intentionally does NOT call `create_tables()`.

### Frontend (Vercel or Railway)
- Vercel: standard Next.js project, root `frontend/`.
- Railway alt: `frontend/railway.toml` already configured (`npm install && npm run build`, `npm start`).
- Set `NEXT_PUBLIC_API_URL` to backend URL.

## Known gotchas

- **`create_tables()` only runs in non-production** (see `app/main.py` startup). Production schema is owned by Alembic — running `create_all` against a migrated DB can stall.
- **Startup is non-blocking by design**: DB and ML model failures are caught and logged so `/health` always responds. Look for `create_tables failed` / `ml_model load failed` in structlog JSON output to diagnose.
- **`MODEL_CACHE_DIR`** (default `model_cache/`) must be writable. Dockerfile creates `/app/model_cache`. Without a trained model the engine still works using market consensus only — `get_ml_model().load()` returns False and inference skips ML.
- **CORS**: `CORS_ORIGINS` is comma-separated string in env; parsed into list in `config.cors_origins_list`. Default is `http://localhost:3000` only — set this in Railway for the production frontend domain.
- **`PORT`**: every start command uses `${PORT:-8000}` so containers run locally without Railway injection.
- **Stripe webhook**: `STRIPE_WEBHOOK_SECRET` must match the endpoint configured in the Stripe dashboard or signature verification fails silently.

## Recent fixes (branch `claude/add-claude-documentation-TnIj6`)

- `56f954f` — startup hardened: skip `create_tables()` in prod, swallow non-fatal errors, raise Railway healthcheck timeout 30→300s.
- `4a0a6fa` — Dockerfile now has a CMD (was empty → instant container exit when Railway picked Docker builder); nixpacks pins Python 3.12 + gcc.

If healthcheck fails again, in order:
1. Confirm Railway service root = `backend/`.
2. Check deploy logs for `Uvicorn running on http://0.0.0.0:…`. If absent, the traceback above it tells you which env var is missing.
3. Confirm `DATABASE_URL` and `SECRET_KEY` are set in Railway variables.
4. Confirm `healthcheckPath` in the Railway UI hasn't been overridden away from `/health`.
