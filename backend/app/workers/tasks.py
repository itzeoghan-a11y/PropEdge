"""
Celery task definitions.

Scheduled tasks (via beat):
  - collect_odds          every 30s (or ODDS_POLL_INTERVAL)
  - run_analysis          every 2 min
  - detect_steam_all      every 60s
  - ingest_game_logs      every hour
  - send_pending_alerts   every 60s

Ad-hoc tasks:
  - train_ml_model        triggered manually / nightly
  - resolve_props         triggered after game completion
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx
from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)

celery_app = Celery(
    "propedge",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    "collect-odds": {
        "task": "app.workers.tasks.collect_odds",
        "schedule": settings.odds_poll_interval,
    },
    "run-analysis": {
        "task": "app.workers.tasks.run_analysis",
        "schedule": 120,   # every 2 minutes
    },
    "detect-steam": {
        "task": "app.workers.tasks.detect_steam_all",
        "schedule": 60,
    },
    "send-alerts": {
        "task": "app.workers.tasks.send_pending_alerts",
        "schedule": 60,
    },
    "ingest-game-logs": {
        "task": "app.workers.tasks.ingest_game_logs",
        "schedule": crontab(minute=0, hour="*/1"),   # hourly
    },
    "train-ml-model": {
        "task": "app.workers.tasks.train_ml_model",
        "schedule": crontab(hour=3, minute=0),       # 3am UTC daily
    },
}


def _run_async(coro):
    """Helper to run async code from a sync Celery task."""
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.workers.tasks.collect_odds", bind=True, max_retries=3)
def collect_odds(self):
    """Fetch latest odds from The Odds API and write snapshots."""
    from app.database import AsyncSessionLocal
    from app.services.ingestion.odds_collector import OddsCollector

    async def _run():
        async with httpx.AsyncClient() as http_client:
            collector = OddsCollector(http_client)
            async with AsyncSessionLocal() as db:
                n = await collector.collect_all(db)
                await db.commit()
                log.info("Odds collection complete: %d snapshots written", n)
                return n

    try:
        return _run_async(_run())
    except Exception as exc:
        log.error("collect_odds failed: %s", exc)
        raise self.retry(exc=exc, countdown=15)


@celery_app.task(name="app.workers.tasks.run_analysis", bind=True)
def run_analysis(self):
    """Run EV analysis on all active props."""
    from app.database import AsyncSessionLocal
    from app.services.ev_engine import analyse_all_active

    async def _run():
        async with AsyncSessionLocal() as db:
            results = await analyse_all_active(db)
            return len(results)

    try:
        n = _run_async(_run())
        log.info("Analysis complete: %d EV opportunities found", n)
        return n
    except Exception as exc:
        log.error("run_analysis failed: %s", exc)


@celery_app.task(name="app.workers.tasks.detect_steam_all", bind=True)
def detect_steam_all(self):
    """Detect steam moves across all active props."""
    from app.database import AsyncSessionLocal
    from app.services.market.steam_detector import scan_all_props_for_steam

    async def _run():
        async with AsyncSessionLocal() as db:
            return await scan_all_props_for_steam(db)

    try:
        n = _run_async(_run())
        log.info("Steam scan complete: %d alerts", n)
        return n
    except Exception as exc:
        log.error("detect_steam_all failed: %s", exc)


@celery_app.task(name="app.workers.tasks.send_pending_alerts", bind=True)
def send_pending_alerts(self):
    """Send Discord/email alerts for unalerted EV opportunities."""
    from app.database import AsyncSessionLocal
    from app.services.alerts import dispatch_pending_alerts

    async def _run():
        async with AsyncSessionLocal() as db:
            return await dispatch_pending_alerts(db)

    try:
        return _run_async(_run())
    except Exception as exc:
        log.error("send_pending_alerts failed: %s", exc)


@celery_app.task(name="app.workers.tasks.ingest_game_logs", bind=True)
def ingest_game_logs(self):
    """Pull recent game logs for all active players."""
    from app.database import AsyncSessionLocal
    from app.services.ingestion.sports_data import SportsDataCollector

    async def _run():
        async with httpx.AsyncClient() as http_client:
            collector = SportsDataCollector(http_client)
            async with AsyncSessionLocal() as db:
                total = 0
                for sport in settings.active_sports:
                    n = await collector.ingest_recent_logs(sport, db)
                    total += n
                await db.commit()
                return total

    try:
        n = _run_async(_run())
        log.info("Game log ingestion complete: %d records", n)
        return n
    except Exception as exc:
        log.error("ingest_game_logs failed: %s", exc)


@celery_app.task(name="app.workers.tasks.train_ml_model", bind=True)
def train_ml_model(self):
    """Nightly ML model retraining from historical resolved bets."""
    if not settings.enable_ml_model:
        return {"skipped": True}

    from app.database import AsyncSessionLocal
    from app.services.modeling.ml_model import get_ml_model
    import numpy as np

    async def _build_dataset():
        from sqlalchemy import select, and_
        from app.models import EVOpportunity, Prop, PlayerGameLog, Player
        from app.services.features.engineer import compute_features
        from app.models import OddsSnapshot

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EVOpportunity, Prop)
                .join(Prop, EVOpportunity.prop_id == Prop.id)
                .where(
                    and_(
                        EVOpportunity.resolved.is_(True),
                        EVOpportunity.won.is_not(None),
                    )
                )
                .limit(50000)
            )
            rows = result.all()

            X_rows = []
            y_rows = []
            for opp, prop in rows:
                f = opp  # features are stored in ModelPrediction, simplified here
                if opp.model_prob is not None:
                    # In production, reconstruct full features from ModelPrediction.features
                    feature_vec = [opp.model_prob, opp.implied_prob, opp.confidence_score]
                    if len(feature_vec) > 0:
                        X_rows.append(feature_vec)
                        y_rows.append(int(opp.won))

            return np.array(X_rows), np.array(y_rows)

    try:
        X, y = _run_async(_build_dataset())
        if len(X) < 500:
            log.info("Insufficient data for ML training (%d samples)", len(X))
            return {"skipped": True, "reason": "insufficient_data", "n": len(X)}

        ml = get_ml_model()
        metrics = ml.train(X, y)
        log.info("ML model retrained: %s", metrics)
        return metrics
    except Exception as exc:
        log.error("train_ml_model failed: %s", exc)
