"""
Props router.

GET /props             — filtered prop list (dashboard table)
GET /props/top         — highest EV props right now
GET /props/steam       — recent steam alerts
GET /props/{id}        — full prop detail
GET /props/arbitrage   — cross-book arbitrage opportunities
POST /props/{id}/result — resolve a prop with actual result (admin)
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_pro
from app.database import get_db
from app.models import EVOpportunity, OddsSnapshot, Player, Prop, SteamAlert
from app.models.prop import ModelPrediction
from app.schemas.props import (
    EVOpportunityOut,
    OddsOut,
    PropDetailOut,
    PropFilter,
    PropSummaryOut,
    SteamAlertOut,
    ModelBreakdownOut,
)
from app.models.user import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/props", tags=["props"])


@router.get("", response_model=list[PropSummaryOut])
async def list_props(
    sport: str | None = None,
    stat_type: str | None = None,
    min_ev: float = Query(default=0.03, ge=0.0),
    min_confidence: float = Query(default=50.0, ge=0.0, le=100.0),
    bookmaker: str | None = None,
    tier: str | None = None,
    direction: str | None = None,
    game_date: date | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns props with at least one EV opportunity meeting the filter criteria.
    Free tier is limited to 5 results per request.
    """
    effective_limit = min(limit, current_user.daily_prop_limit or limit)

    # Join EVOpportunity → Prop → Player
    query = (
        select(EVOpportunity, Prop, Player)
        .join(Prop, EVOpportunity.prop_id == Prop.id)
        .join(Player, Prop.player_id == Player.id)
        .where(
            and_(
                EVOpportunity.edge >= min_ev,
                EVOpportunity.confidence_score >= min_confidence,
                Prop.is_active.is_(True),
            )
        )
        .order_by(desc(EVOpportunity.ev))
    )

    if sport:
        query = query.where(Prop.sport == sport)
    if stat_type:
        query = query.where(Prop.stat_type == stat_type)
    if bookmaker:
        query = query.where(EVOpportunity.bookmaker == bookmaker)
    if tier:
        query = query.where(EVOpportunity.tier == tier)
    if direction:
        query = query.where(EVOpportunity.direction == direction)
    if game_date:
        query = query.where(Prop.game_date == game_date)

    query = query.limit(effective_limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    # Check steam status per prop (use a set lookup)
    prop_ids = {row.Prop.id for row in rows}
    steam_result = await db.execute(
        select(SteamAlert.prop_id).where(
            and_(
                SteamAlert.prop_id.in_(prop_ids),
                SteamAlert.detected_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
            )
        ).distinct()
    )
    props_with_steam: set[int] = set(steam_result.scalars().all())

    summaries: list[PropSummaryOut] = []
    for row in rows:
        opp, prop, player = row.EVOpportunity, row.Prop, row.Player
        summaries.append(PropSummaryOut(
            id=prop.id,
            player_id=player.id,
            player_name=player.name,
            sport=prop.sport,
            stat_type=prop.stat_type,
            line=prop.line,
            game_date=prop.game_date,
            opponent_team=prop.opponent_team,
            best_direction=opp.direction,
            best_bookmaker=opp.bookmaker,
            best_book_odds=opp.book_odds,
            model_prob=opp.model_prob,
            implied_prob=opp.implied_prob,
            edge=opp.edge,
            ev=opp.ev,
            confidence=opp.confidence_score,
            tier=opp.tier,
            sharp_prob=opp.sharp_prob,
            has_steam=prop.id in props_with_steam,
            is_overdue=prop.game_date < date.today(),
        ))

    return summaries


@router.get("/top", response_model=list[PropSummaryOut])
async def top_props(
    limit: int = Query(default=10, le=25),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top 10 highest-EV props right now, minimum elite confidence."""
    return await list_props(
        min_ev=0.05,
        min_confidence=65.0,
        limit=limit,
        offset=0,
        db=db,
        current_user=current_user,
    )


@router.get("/steam", response_model=list[SteamAlertOut])
async def steam_alerts(
    hours_back: int = Query(default=6, le=48),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pro),  # pro+ only
):
    """Recent steam moves."""
    cutoff = datetime.utcnow().__class__.utcnow()
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)

    result = await db.execute(
        select(SteamAlert)
        .where(SteamAlert.detected_at >= cutoff)
        .order_by(desc(SteamAlert.detected_at))
        .limit(limit)
    )
    alerts = result.scalars().all()
    return [
        SteamAlertOut(
            id=a.id,
            direction=a.direction,
            books_moved=a.books_moved,
            line_before=a.line_before,
            line_after=a.line_after,
            line_delta=a.line_delta,
            velocity=a.velocity,
            detected_at=a.detected_at,
        )
        for a in alerts
    ]


@router.get("/{prop_id}", response_model=PropDetailOut)
async def prop_detail(
    prop_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full prop detail including model breakdown, odds, game log context."""
    # Load prop + player
    result = await db.execute(
        select(Prop, Player)
        .join(Player, Prop.player_id == Player.id)
        .where(Prop.id == prop_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Prop not found")

    prop, player = row

    # EV opportunities
    ev_result = await db.execute(
        select(EVOpportunity)
        .where(EVOpportunity.prop_id == prop_id)
        .order_by(desc(EVOpportunity.ev))
    )
    ev_opps = ev_result.scalars().all()

    # Latest odds
    snaps_result = await db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.prop_id == prop_id)
        .order_by(desc(OddsSnapshot.recorded_at))
        .limit(50)
    )
    all_snaps = snaps_result.scalars().all()
    seen: set[str] = set()
    latest_odds: list[OddsSnapshot] = []
    for s in all_snaps:
        if s.bookmaker not in seen:
            latest_odds.append(s)
            seen.add(s.bookmaker)

    # Steam alerts
    steam_result = await db.execute(
        select(SteamAlert)
        .where(SteamAlert.prop_id == prop_id)
        .order_by(desc(SteamAlert.detected_at))
        .limit(5)
    )
    steam_alerts_ = steam_result.scalars().all()

    # Latest ensemble prediction
    pred_result = await db.execute(
        select(ModelPrediction)
        .where(
            ModelPrediction.prop_id == prop_id,
            ModelPrediction.model_type == "ensemble",
        )
        .order_by(desc(ModelPrediction.created_at))
        .limit(1)
    )
    pred = pred_result.scalar_one_or_none()

    model_breakdown: ModelBreakdownOut | None = None
    rolling_avg_5 = rolling_avg_10 = rolling_std_10 = None
    hit_rate_line = opp_def_rank_pct = sharp_soft_deviation = None
    sample_size = 0

    if pred:
        f = pred.features or {}
        rolling_avg_5 = f.get("rolling_avg_5")
        rolling_avg_10 = f.get("rolling_avg_10")
        rolling_std_10 = f.get("rolling_std_10")
        hit_rate_line = f.get("hit_rate_line")
        opp_def_rank_pct = f.get("opp_def_rank_pct")
        sharp_soft_deviation = f.get("sharp_soft_deviation")
        sample_size = f.get("sample_size", 0)
        # Build model breakdown from best EV opportunity + prediction
        if ev_opps:
            best = ev_opps[0]
            model_breakdown = ModelBreakdownOut(
                distribution_prob=None,
                bayesian_prob=None,
                ml_prob=None,
                sharp_prob=best.sharp_prob,
                final_prob_over=pred.predicted_prob_over,
                confidence=pred.confidence,
                model_agreement=0.0,
                n_models=1,
                weights_used={},
            )

    return PropDetailOut(
        id=prop.id,
        player_id=player.id,
        player_name=player.name,
        sport=prop.sport,
        stat_type=prop.stat_type,
        line=prop.line,
        game_date=prop.game_date,
        opponent_team=prop.opponent_team,
        ev_opportunities=[
            EVOpportunityOut(
                id=o.id,
                direction=o.direction,
                bookmaker=o.bookmaker,
                book_odds=o.book_odds,
                implied_prob=o.implied_prob,
                model_prob=o.model_prob,
                edge=o.edge,
                ev=o.ev,
                confidence_score=o.confidence_score,
                tier=o.tier,
                sharp_prob=o.sharp_prob,
                sharp_deviation=o.sharp_deviation,
                found_at=o.found_at,
            )
            for o in ev_opps
        ],
        model_breakdown=model_breakdown,
        latest_odds=[
            OddsOut(
                bookmaker=s.bookmaker,
                line=s.line,
                odds_over=s.odds_over,
                odds_under=s.odds_under,
                implied_prob_over=s.implied_prob_over,
                is_sharp=s.is_sharp,
                recorded_at=s.recorded_at,
            )
            for s in latest_odds
        ],
        steam_alerts=[
            SteamAlertOut(
                id=a.id,
                direction=a.direction,
                books_moved=a.books_moved,
                line_before=a.line_before,
                line_after=a.line_after,
                line_delta=a.line_delta,
                velocity=a.velocity,
                detected_at=a.detected_at,
            )
            for a in steam_alerts_
        ],
        rolling_avg_5=rolling_avg_5,
        rolling_avg_10=rolling_avg_10,
        rolling_std_10=rolling_std_10,
        hit_rate_line=hit_rate_line,
        opp_def_rank_pct=opp_def_rank_pct,
        sharp_soft_deviation=sharp_soft_deviation,
        sample_size=sample_size,
    )


@router.post("/{prop_id}/result", status_code=204)
async def resolve_prop(
    prop_id: int,
    actual_result: float,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin endpoint: set actual result and resolve EV opportunities."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser only")

    result = await db.execute(select(Prop).where(Prop.id == prop_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Prop not found")

    prop.actual_result = actual_result

    ev_result = await db.execute(
        select(EVOpportunity).where(EVOpportunity.prop_id == prop_id)
    )
    for opp in ev_result.scalars().all():
        hit = actual_result > prop.line
        opp.won = hit if opp.direction == "over" else not hit
        opp.resolved = True
