"""
EV Engine — the core analysis pipeline.

For each active Prop, this module:
  1. Loads features (PropFeatures)
  2. Runs the ensemble model
  3. Evaluates EV for every bookmaker line
  4. Persists ModelPrediction + EVOpportunity records
  5. Returns a structured result suitable for the API and alerting

EV Formula
----------
For a bet paying decimal odds D at true probability p:

  EV per unit = p × (D − 1) − (1 − p) × 1
              = p × D − 1

  Edge = p_model − p_implied

Tier classification
-------------------
  standard  : edge >= MIN_EV_THRESHOLD      (e.g. 3%)
  high      : edge >= 0.08                  (8%)
  elite     : edge >= 0.15                  (15%)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    EVOpportunity,
    ModelPrediction,
    OddsSnapshot,
    Player,
    PlayerGameLog,
    Prop,
    TeamDefenseRanking,
)
from app.services.features.engineer import PropFeatures, compute_features
from app.services.modeling.ensemble import EnsembleResult, run_ensemble
from app.services.modeling.ml_model import get_ml_model

log = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PropAnalysisResult:
    prop_id: int
    player_name: str
    stat_type: str
    line: float
    sport: str
    game_date: datetime

    ensemble: EnsembleResult
    features: PropFeatures

    ev_opportunities: list[EVOpportunityResult]

    @property
    def best_ev(self) -> "EVOpportunityResult | None":
        if not self.ev_opportunities:
            return None
        return max(self.ev_opportunities, key=lambda e: e.ev)


@dataclass
class EVOpportunityResult:
    direction: str           # "over" | "under"
    bookmaker: str
    book_odds: float
    implied_prob: float
    model_prob: float
    edge: float
    ev: float
    confidence: float
    tier: str
    sharp_prob: float | None
    sharp_deviation: float | None


def _remove_vig(odds_over: float, odds_under: float) -> tuple[float, float]:
    """Strip vig from a two-sided market. Returns (fair_prob_over, fair_prob_under)."""
    imp_over  = 1 / odds_over  if odds_over  > 1 else 0.5
    imp_under = 1 / odds_under if odds_under > 1 else 0.5
    total = imp_over + imp_under
    return imp_over / total, imp_under / total


def _classify_tier(edge: float) -> str:
    if edge >= 0.15:
        return "elite"
    if edge >= 0.08:
        return "high"
    return "standard"


async def analyse_prop(prop_id: int, db: AsyncSession) -> PropAnalysisResult | None:
    """
    Full analysis pipeline for one prop.
    Writes ModelPrediction + EVOpportunity rows to DB.
    """
    # Load prop + player
    result = await db.execute(
        select(Prop, Player)
        .join(Player, Prop.player_id == Player.id)
        .where(Prop.id == prop_id)
    )
    row = result.first()
    if row is None:
        return None

    prop, player = row

    # Load game logs
    logs_result = await db.execute(
        select(PlayerGameLog)
        .where(PlayerGameLog.player_id == player.id)
        .order_by(PlayerGameLog.game_date.asc())
    )
    game_logs: list[PlayerGameLog] = list(logs_result.scalars().all())

    # Load latest snapshots (one per bookmaker — pick most recent)
    snaps_result = await db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.prop_id == prop_id)
        .order_by(OddsSnapshot.recorded_at.desc())
    )
    all_snapshots = list(snaps_result.scalars().all())
    # Deduplicate: keep only latest per bookmaker
    seen_books: set[str] = set()
    snapshots: list[OddsSnapshot] = []
    for s in all_snapshots:
        if s.bookmaker not in seen_books:
            snapshots.append(s)
            seen_books.add(s.bookmaker)

    # Defense ranking
    def_result = await db.execute(
        select(TeamDefenseRanking).where(
            TeamDefenseRanking.sport == prop.sport,
            TeamDefenseRanking.team_abbr == prop.opponent_team,
            TeamDefenseRanking.stat_type == prop.stat_type,
        )
    )
    def_row = def_result.scalar_one_or_none()
    defense_rank_pct = (def_row.rank - 1) / 29 if def_row else None  # 0=elite,1=worst

    # Feature engineering
    features = compute_features(
        prop=prop,
        game_logs=game_logs,
        snapshots=snapshots,
        defense_rank_pct=defense_rank_pct,
        sharp_books=settings.sharp_books,
    )

    # Historical stat values
    stat_values_all: list[float] = []
    stat_values_recent: list[float] = []
    for gl in game_logs:
        v = getattr(gl, prop.stat_type, None)
        if v is not None:
            stat_values_all.append(float(v))
    stat_values_recent = stat_values_all[-10:]

    # Ensemble
    ml_model = get_ml_model()
    ensemble = run_ensemble(
        features=features,
        historical_all=stat_values_all,
        historical_recent=stat_values_recent,
        ml_model=ml_model,
    )

    # Persist ensemble prediction
    prediction = ModelPrediction(
        prop_id=prop_id,
        model_type="ensemble",
        predicted_prob_over=ensemble.final_prob_over,
        confidence=ensemble.confidence,
        sample_size=features.sample_size,
        features=features.to_dict(),
    )
    db.add(prediction)

    # ── EV evaluation per bookmaker ───────────────────────────────
    ev_results: list[EVOpportunityResult] = []

    for snap in snapshots:
        if snap.bookmaker in settings.sharp_books:
            continue   # don't bet into sharp books

        fair_over, fair_under = _remove_vig(snap.odds_over, snap.odds_under)

        for direction, model_p, fair_p, book_odds in [
            ("over",  ensemble.final_prob_over,       fair_over,  snap.odds_over),
            ("under", 1 - ensemble.final_prob_over,   fair_under, snap.odds_under),
        ]:
            implied_p = 1 / book_odds if book_odds > 1 else 0.5
            edge = model_p - implied_p
            ev   = model_p * book_odds - 1   # per unit

            if edge < settings.min_ev_threshold:
                continue
            if ensemble.confidence < settings.min_confidence_threshold:
                continue

            sharp_dev = None
            if ensemble.sharp_prob is not None:
                sharp_p = ensemble.sharp_prob if direction == "over" else (1 - ensemble.sharp_prob)
                sharp_dev = model_p - sharp_p

            ev_result = EVOpportunityResult(
                direction=direction,
                bookmaker=snap.bookmaker,
                book_odds=snap.odds_over if direction == "over" else snap.odds_under,
                implied_prob=implied_p,
                model_prob=model_p,
                edge=edge,
                ev=ev,
                confidence=ensemble.confidence,
                tier=_classify_tier(edge),
                sharp_prob=ensemble.sharp_prob,
                sharp_deviation=sharp_dev,
            )
            ev_results.append(ev_result)

            # Persist
            opp = EVOpportunity(
                prop_id=prop_id,
                direction=direction,
                bookmaker=snap.bookmaker,
                book_odds=book_odds,
                implied_prob=implied_p,
                model_prob=model_p,
                edge=edge,
                ev=ev,
                confidence_score=ensemble.confidence,
                tier=_classify_tier(edge),
                sharp_prob=ensemble.sharp_prob,
                sharp_deviation=sharp_dev,
            )
            db.add(opp)

    await db.flush()

    return PropAnalysisResult(
        prop_id=prop_id,
        player_name=player.name,
        stat_type=prop.stat_type,
        line=prop.line,
        sport=prop.sport,
        game_date=prop.game_date,
        ensemble=ensemble,
        features=features,
        ev_opportunities=sorted(ev_results, key=lambda e: e.ev, reverse=True),
    )


async def analyse_all_active(db: AsyncSession) -> list[PropAnalysisResult]:
    """Run analysis on all active props. Returns list of results with EV opportunities."""
    prop_ids_result = await db.execute(
        select(Prop.id).where(Prop.is_active.is_(True))
    )
    prop_ids = list(prop_ids_result.scalars().all())

    results: list[PropAnalysisResult] = []
    for pid in prop_ids:
        try:
            result = await analyse_prop(pid, db)
            if result and result.ev_opportunities:
                results.append(result)
        except Exception as exc:
            log.error("Analysis failed for prop %d: %s", pid, exc)

    await db.commit()
    log.info("Analysis complete: %d props analysed, %d with EV", len(prop_ids), len(results))
    return results
