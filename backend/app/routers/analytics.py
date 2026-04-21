from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_optional, require_pro
from app.database import get_db
from app.models import EVOpportunity, Player, Prop, SteamAlert
from app.models.prop import BacktestResult
from app.models.user import User
from app.services.backtesting import run_backtest

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/performance")
async def performance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """High-level performance stats for the platform."""
    today = date.today()
    week_ago = today - timedelta(days=7)

    # Total resolved bets
    total_resolved = await db.execute(
        select(func.count()).where(EVOpportunity.resolved.is_(True))
    )
    # Win rate
    wins = await db.execute(
        select(func.count()).where(EVOpportunity.resolved.is_(True), EVOpportunity.won.is_(True))
    )
    # Weekly EV opps
    weekly_opps = await db.execute(
        select(func.count()).where(EVOpportunity.found_at >= week_ago)
    )
    # Weekly steam
    weekly_steam = await db.execute(
        select(func.count()).where(SteamAlert.detected_at >= week_ago)
    )

    n_resolved = total_resolved.scalar() or 0
    n_wins     = wins.scalar() or 0

    return {
        "total_resolved_bets": n_resolved,
        "overall_win_rate":    n_wins / n_resolved if n_resolved > 0 else None,
        "weekly_ev_opportunities": weekly_opps.scalar() or 0,
        "weekly_steam_alerts": weekly_steam.scalar() or 0,
    }


@router.get("/backtest")
async def backtest(
    date_from: date = Query(default=date.today() - timedelta(days=30)),
    date_to:   date = Query(default=date.today()),
    sport:     str | None = None,
    stat_type: str | None = None,
    min_edge:  float = 0.03,
    min_confidence: float = 50.0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pro),
):
    """Run backtesting over resolved historical bets."""
    metrics = await run_backtest(
        db,
        date_from=date_from,
        date_to=date_to,
        sport=sport,
        stat_type=stat_type,
        min_edge=min_edge,
        min_confidence=min_confidence,
    )
    return {
        "n_bets":         metrics.n_bets,
        "win_rate":       metrics.win_rate,
        "roi":            metrics.roi,
        "avg_ev":         metrics.avg_ev,
        "avg_confidence": metrics.avg_confidence,
        "brier_score":    metrics.brier_score,
        "tier_breakdown": metrics.tier_breakdown,
        "book_breakdown": metrics.book_breakdown,
    }


@router.get("/backtest/history")
async def backtest_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pro),
):
    result = await db.execute(
        select(BacktestResult)
        .order_by(BacktestResult.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "label": r.run_label,
            "date_from": r.date_from,
            "date_to": r.date_to,
            "total_bets": r.total_bets,
            "win_rate": r.win_rate,
            "roi": r.roi,
            "brier_score": r.calibration_error,
            "created_at": r.created_at,
        }
        for r in rows
    ]
