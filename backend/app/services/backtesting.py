"""
Backtesting Engine.

Replays historical EVOpportunity records against actual prop results
and computes performance metrics.

Metrics
-------
- Win rate          : bets won / total bets
- ROI               : (profit - stake) / stake  (flat $1 betting)
- Average EV        : mean predicted EV
- Calibration error : Brier score (how well model probabilities match outcomes)
- CLV               : closing line value — did we beat the closing price?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EVOpportunity, Prop
from app.models.prop import BacktestResult

log = logging.getLogger(__name__)


@dataclass
class BacktestMetrics:
    label: str
    n_bets: int
    win_rate: float
    roi: float
    avg_ev: float
    avg_confidence: float
    brier_score: float
    tier_breakdown: dict[str, dict[str, float]]   # tier → {n, win_rate, roi}
    book_breakdown: dict[str, dict[str, float]]


async def run_backtest(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    sport: str | None = None,
    stat_type: str | None = None,
    min_edge: float = 0.03,
    min_confidence: float = 50.0,
    label: str = "backtest",
) -> BacktestMetrics:
    """
    Backtest all resolved EVOpportunity records in the date range.
    An EV opportunity is "resolved" when Prop.actual_result is set.
    """
    query = (
        select(EVOpportunity, Prop)
        .join(Prop, EVOpportunity.prop_id == Prop.id)
        .where(
            and_(
                EVOpportunity.resolved.is_(True),
                EVOpportunity.edge >= min_edge,
                EVOpportunity.confidence_score >= min_confidence,
                Prop.game_date >= date_from,
                Prop.game_date <= date_to,
            )
        )
    )
    if sport:
        query = query.where(Prop.sport == sport)
    if stat_type:
        query = query.where(Prop.stat_type == stat_type)

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return BacktestMetrics(
            label=label,
            n_bets=0,
            win_rate=0.0,
            roi=0.0,
            avg_ev=0.0,
            avg_confidence=0.0,
            brier_score=0.5,
            tier_breakdown={},
            book_breakdown={},
        )

    wins       = 0
    total_pnl  = 0.0
    model_probs: list[float] = []
    outcomes:   list[int]   = []
    ev_vals:    list[float] = []
    conf_vals:  list[float] = []

    tier_data: dict[str, list] = {}
    book_data: dict[str, list] = {}

    for opp, prop in rows:
        if prop.actual_result is None or opp.won is None:
            continue

        won_int = int(opp.won)
        pnl = (opp.book_odds - 1) if opp.won else -1.0

        wins      += won_int
        total_pnl += pnl
        model_probs.append(opp.model_prob)
        outcomes.append(won_int)
        ev_vals.append(opp.ev)
        conf_vals.append(opp.confidence_score)

        # Tier breakdown
        t = opp.tier
        if t not in tier_data:
            tier_data[t] = []
        tier_data[t].append((won_int, pnl))

        # Book breakdown
        b = opp.bookmaker
        if b not in book_data:
            book_data[b] = []
        book_data[b].append((won_int, pnl))

    n = len(outcomes)
    if n == 0:
        return BacktestMetrics(
            label=label, n_bets=0, win_rate=0, roi=0,
            avg_ev=0, avg_confidence=0, brier_score=0.5,
            tier_breakdown={}, book_breakdown={},
        )

    brier = float(np.mean(
        [(p - y) ** 2 for p, y in zip(model_probs, outcomes)]
    ))

    def _aggregate(data: list[tuple[int, float]]) -> dict[str, float]:
        n_ = len(data)
        wins_ = sum(d[0] for d in data)
        pnl_  = sum(d[1] for d in data)
        return {
            "n":        n_,
            "win_rate": wins_ / n_ if n_ else 0.0,
            "roi":      pnl_ / n_ if n_ else 0.0,
        }

    metrics = BacktestMetrics(
        label=label,
        n_bets=n,
        win_rate=wins / n,
        roi=total_pnl / n,
        avg_ev=float(np.mean(ev_vals)),
        avg_confidence=float(np.mean(conf_vals)),
        brier_score=brier,
        tier_breakdown={k: _aggregate(v) for k, v in tier_data.items()},
        book_breakdown={k: _aggregate(v) for k, v in book_data.items()},
    )

    # Persist summary
    bt_record = BacktestResult(
        run_label=label,
        sport=sport,
        stat_type=stat_type,
        date_from=date_from,
        date_to=date_to,
        total_bets=n,
        win_rate=metrics.win_rate,
        roi=metrics.roi,
        avg_ev=metrics.avg_ev,
        avg_confidence=metrics.avg_confidence,
        calibration_error=brier,
        parameters={
            "min_edge": min_edge,
            "min_confidence": min_confidence,
        },
    )
    db.add(bt_record)
    await db.commit()

    log.info(
        "Backtest '%s': N=%d  WR=%.1f%%  ROI=%.2f%%  Brier=%.4f",
        label, n, metrics.win_rate * 100, metrics.roi * 100, brier,
    )
    return metrics
