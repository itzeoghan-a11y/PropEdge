"""
Props router.

GET /props             — filtered prop list (dashboard table)
GET /props/top         — highest EV props right now
GET /props/steam       — recent steam alerts
GET /props/line-shop   — cross-book line shopping view (best available numbers)
GET /props/{id}        — full prop detail
POST /props/{id}/result — resolve a prop with actual result (admin)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_pro
from app.database import get_db
from app.models import EVOpportunity, OddsSnapshot, Player, Prop, SteamAlert
from app.models.prop import ModelPrediction
from app.schemas.props import (
    BookDetailOut,
    EVOpportunityOut,
    LineShopping,
    ModelBreakdownOut,
    OddsOut,
    PropDetailOut,
    PropFilter,
    PropSummaryOut,
    SteamAlertOut,
)
from app.models.user import User
from app.services.market.line_shopper import compute_line_shopping
from app.config import get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/props", tags=["props"])
settings = get_settings()


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
    best_available_only: bool = False,
    has_steam: bool | None = None,
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
    if best_available_only:
        query = query.where(EVOpportunity.is_best_available_line.is_(True))

    query = query.limit(effective_limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    # Steam status per prop
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

    # Filter by has_steam after gathering the set
    summaries: list[PropSummaryOut] = []
    for row in rows:
        opp, prop, player = row.EVOpportunity, row.Prop, row.Player
        prop_has_steam = prop.id in props_with_steam

        if has_steam is True and not prop_has_steam:
            continue
        if has_steam is False and prop_has_steam:
            continue

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
            # Line shopping summary from Prop columns
            best_over_book=prop.best_over_book,
            best_over_odds=prop.best_over_odds,
            best_under_book=prop.best_under_book,
            best_under_odds=prop.best_under_odds,
            consensus_line=prop.consensus_line,
            line_dispersion=prop.line_dispersion,
            soft_book_count=prop.soft_book_count,
            has_steam=prop_has_steam,
            steam_boosted=opp.steam_boosted,
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


@router.get("/line-shop", response_model=list[PropSummaryOut])
async def line_shop(
    sport: str | None = None,
    stat_type: str | None = None,
    min_dispersion: float = Query(default=0.5, ge=0.0, description="Min line std-dev across books"),
    min_soft_books: int = Query(default=1, ge=1, description="Min number of soft books"),
    game_date: date | None = None,
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Line shopping view — props where books disagree or a soft number exists.

    Returns props ordered by line dispersion descending (most disagreement first).
    A high dispersion or multiple soft books means there's a stale line somewhere
    that the sharp market has already moved past.
    """
    query = (
        select(Prop, Player)
        .join(Player, Prop.player_id == Player.id)
        .where(Prop.is_active.is_(True))
    )

    if sport:
        query = query.where(Prop.sport == sport)
    if stat_type:
        query = query.where(Prop.stat_type == stat_type)
    if game_date:
        query = query.where(Prop.game_date == game_date)
    if min_dispersion > 0:
        query = query.where(
            Prop.line_dispersion >= min_dispersion
        )
    if min_soft_books > 0:
        query = query.where(
            Prop.soft_book_count >= min_soft_books
        )

    query = query.order_by(desc(Prop.line_dispersion)).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    # Build lightweight summaries focused on line shopping data
    summaries: list[PropSummaryOut] = []
    for row in rows:
        prop, player = row.Prop, row.Player

        # Grab best EV opp for this prop (for ev/edge/confidence fields)
        ev_result = await db.execute(
            select(EVOpportunity)
            .where(EVOpportunity.prop_id == prop.id)
            .order_by(desc(EVOpportunity.ev))
            .limit(1)
        )
        best_opp = ev_result.scalar_one_or_none()

        prop_has_steam = False
        steam_check = await db.execute(
            select(SteamAlert.id).where(
                and_(
                    SteamAlert.prop_id == prop.id,
                    SteamAlert.detected_at >= datetime.utcnow() - timedelta(hours=6),
                )
            ).limit(1)
        )
        if steam_check.scalar_one_or_none():
            prop_has_steam = True

        summaries.append(PropSummaryOut(
            id=prop.id,
            player_id=player.id,
            player_name=player.name,
            sport=prop.sport,
            stat_type=prop.stat_type,
            line=prop.line,
            game_date=prop.game_date,
            opponent_team=prop.opponent_team,
            best_direction=best_opp.direction if best_opp else None,
            best_bookmaker=best_opp.bookmaker if best_opp else None,
            best_book_odds=best_opp.book_odds if best_opp else None,
            model_prob=best_opp.model_prob if best_opp else None,
            implied_prob=best_opp.implied_prob if best_opp else None,
            edge=best_opp.edge if best_opp else None,
            ev=best_opp.ev if best_opp else None,
            confidence=best_opp.confidence_score if best_opp else None,
            tier=best_opp.tier if best_opp else None,
            sharp_prob=best_opp.sharp_prob if best_opp else None,
            best_over_book=prop.best_over_book,
            best_over_odds=prop.best_over_odds,
            best_under_book=prop.best_under_book,
            best_under_odds=prop.best_under_odds,
            consensus_line=prop.consensus_line,
            line_dispersion=prop.line_dispersion,
            soft_book_count=prop.soft_book_count,
            has_steam=prop_has_steam,
            steam_boosted=best_opp.steam_boosted if best_opp else False,
            is_overdue=prop.game_date < date.today(),
        ))

    return summaries


@router.get("/{prop_id}", response_model=PropDetailOut)
async def prop_detail(
    prop_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full prop detail including model breakdown, odds, game log context, and line shopping."""
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

    # Latest odds (one per book)
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

    # Live line shopping from current snapshots
    shopping_result = compute_line_shopping(
        prop_id=prop_id,
        snapshots=latest_odds,
        sharp_books=settings.sharp_books,
    )
    line_shopping_out = LineShopping(
        best_over_book=shopping_result.best_over_book,
        best_over_odds=shopping_result.best_over_odds,
        best_under_book=shopping_result.best_under_book,
        best_under_odds=shopping_result.best_under_odds,
        sharp_line=shopping_result.sharp_line,
        sharp_no_vig_prob_over=shopping_result.sharp_no_vig_prob_over,
        consensus_line=shopping_result.consensus_line,
        consensus_no_vig_prob_over=shopping_result.consensus_no_vig_prob_over,
        line_dispersion=shopping_result.line_dispersion,
        prob_dispersion=shopping_result.prob_dispersion,
        soft_over_books=shopping_result.soft_over_books,
        soft_under_books=shopping_result.soft_under_books,
        book_details=[
            BookDetailOut(**d) for d in shopping_result.book_details
        ],
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
                is_best_available_line=o.is_best_available_line,
                steam_boosted=o.steam_boosted,
                line_at_flag=o.line_at_flag,
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
        line_shopping=line_shopping_out,
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
    closing_line_odds_over: float | None = None,
    closing_line_odds_under: float | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin endpoint: set actual result and resolve EV opportunities.

    Optionally pass closing_line_odds_over/under to capture closing line
    value (CLV) — the final odds right before the game started.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser only")

    result = await db.execute(select(Prop).where(Prop.id == prop_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Prop not found")

    prop.actual_result = actual_result
    prop.is_active = False

    ev_result = await db.execute(
        select(EVOpportunity).where(EVOpportunity.prop_id == prop_id)
    )
    for opp in ev_result.scalars().all():
        hit = actual_result > prop.line
        opp.won = hit if opp.direction == "over" else not hit
        opp.resolved = True

        # Capture closing line odds for CLV calculation if provided
        if opp.direction == "over" and closing_line_odds_over is not None:
            opp.closing_line_odds = closing_line_odds_over
        elif opp.direction == "under" and closing_line_odds_under is not None:
            opp.closing_line_odds = closing_line_odds_under

    await db.commit()
