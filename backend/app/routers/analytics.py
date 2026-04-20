from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_pro
from app.database import get_db
from app.models import EVOpportunity, Player, Prop, SteamAlert
from app.models.prop import BacktestResult
from app.models.user import User
from app.services.backtesting import run_backtest

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/performance")
async def performance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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


@router.get("/history")
async def bet_history(
    date_from: date = Query(default=date.today() - timedelta(days=30)),
    date_to:   date = Query(default=date.today()),
    sport:     str | None = None,
    stat_type: str | None = None,
    tier:      str | None = None,
    bookmaker: str | None = None,
    resolved_only: bool = True,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full bet history — every flagged EV opportunity with P&L and CLV data.

    Returns individual bet records alongside a summary.
    Useful for demonstrating track record and model accuracy to users.
    """
    query = (
        select(EVOpportunity, Prop, Player)
        .join(Prop, EVOpportunity.prop_id == Prop.id)
        .join(Player, Prop.player_id == Player.id)
        .where(
            and_(
                Prop.game_date >= date_from,
                Prop.game_date <= date_to,
            )
        )
        .order_by(desc(EVOpportunity.found_at))
    )

    if resolved_only:
        query = query.where(EVOpportunity.resolved.is_(True))
    if sport:
        query = query.where(Prop.sport == sport)
    if stat_type:
        query = query.where(Prop.stat_type == stat_type)
    if tier:
        query = query.where(EVOpportunity.tier == tier)
    if bookmaker:
        query = query.where(EVOpportunity.bookmaker == bookmaker)

    # Free tier: limit to 25 history rows
    if current_user.tier == "free":
        limit = min(limit, 25)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    bets = []
    total_pnl = 0.0
    wins = 0
    losses = 0

    for row in rows:
        opp, prop, player = row.EVOpportunity, row.Prop, row.Player
        pnl: float | None = None
        if opp.resolved and opp.won is not None:
            pnl = (opp.book_odds - 1) if opp.won else -1.0
            total_pnl += pnl
            if opp.won:
                wins += 1
            else:
                losses += 1

        # Closing line value: did we get better than closing odds?
        clv: float | None = None
        if opp.closing_line_odds is not None and opp.book_odds is not None:
            # CLV = (our odds / closing odds) - 1
            # Positive CLV = we bet at better odds than the closing line
            clv = round((opp.book_odds / opp.closing_line_odds) - 1, 4)

        bets.append({
            "id": opp.id,
            "prop_id": prop.id,
            "player_name": player.name,
            "sport": prop.sport,
            "stat_type": prop.stat_type,
            "line": opp.line_at_flag if opp.line_at_flag is not None else prop.line,
            "direction": opp.direction,
            "bookmaker": opp.bookmaker,
            "book_odds": opp.book_odds,
            "model_prob": round(opp.model_prob, 4),
            "implied_prob": round(opp.implied_prob, 4),
            "edge": round(opp.edge, 4),
            "ev": round(opp.ev, 4),
            "confidence": opp.confidence_score,
            "tier": opp.tier,
            "sharp_prob": opp.sharp_prob,
            "is_best_available_line": opp.is_best_available_line,
            "steam_boosted": opp.steam_boosted,
            "found_at": opp.found_at.isoformat(),
            "game_date": prop.game_date.isoformat(),
            "actual_result": prop.actual_result,
            "resolved": opp.resolved,
            "won": opp.won,
            "pnl": round(pnl, 4) if pnl is not None else None,
            "closing_line_odds": opp.closing_line_odds,
            "clv": clv,
        })

    n_resolved = wins + losses
    summary = {
        "total_flagged": len(bets),
        "resolved": n_resolved,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / n_resolved if n_resolved > 0 else None,
        "total_pnl": round(total_pnl, 4),
        "roi": round(total_pnl / n_resolved, 4) if n_resolved > 0 else None,
    }

    return {"bets": bets, "summary": summary}


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
