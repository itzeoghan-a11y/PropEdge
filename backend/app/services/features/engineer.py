"""
Feature Engineering Pipeline.

Given a Prop and its associated PlayerGameLogs + OddsSnapshots,
produces a flat feature dict ready for the modeling layer.

Features
--------
Performance:
  rolling_avg_5, rolling_avg_10, rolling_avg_season  — rolling averages
  rolling_median_10, rolling_std_10                  — central tendency + spread
  weighted_avg_5                                     — recency-weighted average
  hit_rate_line                                      — fraction above current line

Context:
  minutes_avg_5                                      — projected minutes proxy
  usage_avg_5                                        — usage rate if available
  days_rest                                          — rest days before game
  is_home                                            — home/away flag
  opp_def_rank_pct                                   — opponent defense percentile (0=best)

Market:
  sharp_implied_prob                                 — Pinnacle no-vig prob
  soft_avg_implied_prob                              — soft book average implied
  sharp_soft_deviation                               — difference
  line_vs_rolling_avg                                — line relative to rolling avg
  odds_dispersion                                    — std of implied probs across books
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.models import OddsSnapshot, PlayerGameLog, Prop

log = logging.getLogger(__name__)


@dataclass
class PropFeatures:
    prop_id: int
    stat_type: str
    line: float

    # Performance
    rolling_avg_5: float | None = None
    rolling_avg_10: float | None = None
    rolling_avg_season: float | None = None
    rolling_median_10: float | None = None
    rolling_std_10: float | None = None
    weighted_avg_5: float | None = None
    hit_rate_line: float | None = None     # fraction of games player went OVER the line

    # Playing time / role
    minutes_avg_5: float | None = None
    usage_avg_5: float | None = None

    # Context
    days_rest: int | None = None
    is_home: bool = True
    opp_def_rank_pct: float | None = None  # 0.0 = elite defense, 1.0 = worst

    # Market
    sharp_implied_prob: float | None = None
    soft_avg_implied_prob: float | None = None
    sharp_soft_deviation: float | None = None
    line_vs_rolling_avg: float | None = None   # line - rolling_avg_10
    odds_dispersion: float | None = None

    # Derived
    sample_size: int = 0
    data_quality: float = 0.0     # 0–1, proportion of features present

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    def to_model_array(self, sharp_books: list[str]) -> np.ndarray:
        """Flat float array for sklearn / XGBoost."""
        return np.array([
            self.rolling_avg_5 or 0.0,
            self.rolling_avg_10 or 0.0,
            self.rolling_avg_season or 0.0,
            self.rolling_median_10 or 0.0,
            self.rolling_std_10 or 1.0,
            self.weighted_avg_5 or 0.0,
            self.hit_rate_line or 0.5,
            self.minutes_avg_5 or 30.0,
            self.usage_avg_5 or 20.0,
            float(self.days_rest or 1),
            float(self.is_home),
            self.opp_def_rank_pct or 0.5,
            self.sharp_implied_prob or 0.5,
            self.soft_avg_implied_prob or 0.5,
            self.sharp_soft_deviation or 0.0,
            self.line_vs_rolling_avg or 0.0,
            self.odds_dispersion or 0.0,
            float(self.sample_size),
            self.line,
        ], dtype=np.float32)


_WEIGHTS = np.array([0.35, 0.25, 0.20, 0.12, 0.08])  # most-recent to oldest (5 games)


def _extract_stat(log: PlayerGameLog, stat_type: str) -> float | None:
    return getattr(log, stat_type, None)


def _rolling(values: list[float], n: int) -> float | None:
    window = values[-n:] if len(values) >= n else values
    return float(np.mean(window)) if window else None


def _weighted_avg(values: list[float]) -> float | None:
    if not values:
        return None
    recent = values[-5:]
    if len(recent) == 0:
        return None
    w = _WEIGHTS[-len(recent):]
    w = w / w.sum()
    return float(np.dot(w, recent))


def compute_features(
    prop: Prop,
    game_logs: list[PlayerGameLog],
    snapshots: list[OddsSnapshot],
    defense_rank_pct: float | None,
    sharp_books: list[str],
) -> PropFeatures:
    """
    Main feature engineering entry point.

    Parameters
    ----------
    prop        : the Prop to compute features for
    game_logs   : sorted ascending by game_date (oldest first)
    snapshots   : all recent OddsSnapshot rows for this prop
    defense_rank_pct : opponent defensive rank percentile (0=elite, 1=worst)
    sharp_books : list of bookmaker keys to treat as sharp
    """
    feat = PropFeatures(
        prop_id=prop.id,
        stat_type=prop.stat_type,
        line=prop.line,
    )

    # ── Performance features ──────────────────────────────────────
    raw_values: list[float] = []
    minutes_values: list[float] = []
    usage_values: list[float] = []

    for gl in game_logs:
        v = _extract_stat(gl, prop.stat_type)
        if v is not None:
            raw_values.append(float(v))
        if gl.minutes_played is not None:
            minutes_values.append(float(gl.minutes_played))
        if gl.usage_rate is not None:
            usage_values.append(float(gl.usage_rate))

    feat.sample_size = len(raw_values)

    if raw_values:
        feat.rolling_avg_5     = _rolling(raw_values, 5)
        feat.rolling_avg_10    = _rolling(raw_values, 10)
        feat.rolling_avg_season = float(np.mean(raw_values))
        feat.rolling_median_10  = float(np.median(raw_values[-10:])) if len(raw_values) >= 3 else None
        feat.rolling_std_10     = float(np.std(raw_values[-10:])) if len(raw_values) >= 3 else None
        feat.weighted_avg_5     = _weighted_avg(raw_values)
        feat.hit_rate_line      = float(
            sum(1 for v in raw_values if v > prop.line) / len(raw_values)
        )
        feat.line_vs_rolling_avg = prop.line - (feat.rolling_avg_10 or prop.line)

    if minutes_values:
        feat.minutes_avg_5 = _rolling(minutes_values, 5)

    if usage_values:
        feat.usage_avg_5 = _rolling(usage_values, 5)

    # ── Context features ─────────────────────────────────────────
    feat.opp_def_rank_pct = defense_rank_pct

    # Most recent game log for rest days
    if game_logs:
        last_game = game_logs[-1]
        feat.is_home = last_game.is_home
        feat.days_rest = last_game.days_rest

    # ── Market features ──────────────────────────────────────────
    if snapshots:
        sharp_snaps = [s for s in snapshots if s.bookmaker in sharp_books]
        soft_snaps  = [s for s in snapshots if s.bookmaker not in sharp_books]

        if sharp_snaps:
            # Use the most recent sharp snapshot; remove vig
            sharp = max(sharp_snaps, key=lambda s: s.recorded_at)
            total_implied = sharp.implied_prob_over + sharp.implied_prob_under
            feat.sharp_implied_prob = (
                sharp.implied_prob_over / total_implied if total_implied > 0 else 0.5
            )

        if soft_snaps:
            soft_probs = []
            for s in soft_snaps:
                total = s.implied_prob_over + s.implied_prob_under
                if total > 0:
                    soft_probs.append(s.implied_prob_over / total)
            if soft_probs:
                feat.soft_avg_implied_prob = float(np.mean(soft_probs))
                feat.odds_dispersion = float(np.std(soft_probs)) if len(soft_probs) > 1 else 0.0

        if feat.sharp_implied_prob is not None and feat.soft_avg_implied_prob is not None:
            feat.sharp_soft_deviation = feat.soft_avg_implied_prob - feat.sharp_implied_prob

    # ── Data quality score ───────────────────────────────────────
    fields = [
        feat.rolling_avg_10,
        feat.rolling_std_10,
        feat.sharp_implied_prob,
        feat.soft_avg_implied_prob,
        feat.opp_def_rank_pct,
        feat.minutes_avg_5,
    ]
    feat.data_quality = sum(1 for f in fields if f is not None) / len(fields)

    return feat
