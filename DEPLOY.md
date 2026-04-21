# PropEdge deploy context

Railway (backend, worker, beat) + Vercel (frontend). Branch: `claude/next-deployment-steps-bdm7m`.

## Railway — three services, all from the same repo/branch

| Service | Root Directory | Config-as-code Path | Purpose |
|---------|---------------|----------------------|---------|
| web     | `backend`     | `backend/railway.toml`        | FastAPI + runs `alembic upgrade head` on deploy |
| worker  | `backend`     | `backend/railway.worker.toml` | Celery worker — pulls odds, runs EV analysis |
| beat    | `backend`     | `backend/railway.beat.toml`   | Celery beat — schedules tasks (keep at **1 replica**) |

Config-as-code Path is **relative to repo root**, not Root Directory.

Also add: Postgres plugin, Redis plugin (injects `DATABASE_URL`, `REDIS_URL` into every service).

### Env vars (set on all three services)

| Var | Value |
|-----|-------|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | long random string |
| `ODDS_API_KEY` | from the-odds-api.com dashboard |
| `CORS_ORIGINS` | Vercel URL, e.g. `https://propedge.vercel.app` |

Optional: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_ELITE`, `SPORTS_DATA_API_KEY`, `DISCORD_WEBHOOK_URL`, `SENDGRID_API_KEY`.

## Vercel

- `API_URL` = Railway web service URL (server-only, used by Next.js rewrite)
- Redeploy after setting

Frontend talks to backend via same-origin `/api/*` → Next.js rewrites to `API_URL` → Railway. No CORS involved.

## Smoke test

1. `curl https://<railway-web>/health` → `{"status":"ok"}`
2. Railway worker logs show `Odds collection complete: N snapshots written` every ~30s
3. Vercel site `/api/props` returns 200 (same-origin)
4. `SELECT COUNT(*) FROM odds_snapshots` climbs over time

## Known gotchas (already patched in this branch)

- **asyncpg + sslmode**: Railway's `DATABASE_URL` has `?sslmode=require`; asyncpg rejects it. `config.async_database_url` strips it.
- **Startup hook**: `main.startup` no longer hard-fails on DB/ML errors; skips `create_tables()` in prod (Alembic owns schema).
- **Celery event loop**: `_run_async` creates a fresh loop per task (the old `get_event_loop()` breaks on 3.12+).
- **Alembic**: migrations reuse `Settings.async_database_url` so sslmode is handled there too.

## Odds API budget

Default poll is every 30s × ~20 markets × 4 sports ≈ 2,880 req/hour. Free tier (500/month) won't last an hour. Paid tier (~$30/mo, 20k req) is realistic minimum. Adjust `ODDS_POLL_INTERVAL` env var (seconds) to throttle.

## If a service fails to build

- `Nixpacks unable to generate build plan` → Root Directory isn't `backend`
- `config file X does not exist` → Config path needs `backend/` prefix
- uvicorn crashes immediately → check `DATABASE_URL` is injected (Postgres plugin attached?)
- worker does nothing → check `REDIS_URL` is injected and `ODDS_API_KEY` is set
