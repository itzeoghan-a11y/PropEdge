"""
Ensemble Model.

Combines distribution, Bayesian, ML, and sharp-line models into a single
final probability estimate with a calibrated confidence score.

Weighting strategy
------------------
Each model contributes a weighted vote.  Weights are dynamic:

- Sharp line model always gets >= 25% weight (it reflects real money)
- ML model only contributes if it is loaded and sample_size >= 20
- Distribution / Bayesian models are down-weighted if sample_size < 10
- Model *agreement* boosts confidence; disagreement reduces it

Confidence Score (0–100)
------------------------
- Base: 50
- +10 if all 3+ models agree within 5 pp
- +10 if sharp book prob is available
- +10 if sample_size >= 20
- +10 if data_quality >= 0.8
- +10 if edge is backed by sharp deviation in same direction
- -10 per model that disagrees by > 10 pp from ensemble
- Capped at [0, 100]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.services.features.engineer import PropFeatures
from app.services.modeling.bayesian import BayesianResult, bayesian_prob_over, is_continuous
from app.services.modeling.distribution import DistributionResult, fit_distribution
from app.services.modeling.ml_model import MLModel

log = logging.getLogger(__name__)


@dataclass
class EnsembleResult:
    final_prob_over: float         # 0–1

    # Component probs
    distribution_prob: float | None
    bayesian_prob: float | None
    ml_prob: float | None
    sharp_prob: float | None       # no-vig Pinnacle prob

    # Metadata
    confidence: float              # 0–100
    model_agreement: float         # std of component probs (lower = more agreement)
    n_models: int
    weights_used: dict[str, float]

    # Per-model details
    distribution_result: DistributionResult | None = None
    bayesian_result: BayesianResult | None = None


_BASE_WEIGHTS: dict[str, float] = {
    "distribution": 0.20,
    "bayesian":     0.20,
    "ml":           0.30,
    "sharp":        0.30,
}


def run_ensemble(
    features: PropFeatures,
    historical_all: list[float],
    historical_recent: list[float],
    ml_model: MLModel,
) -> EnsembleResult:
    """
    Run all available models and combine into an ensemble probability.
    """
    probs: dict[str, float] = {}
    weights: dict[str, float] = {}
    dist_result: DistributionResult | None = None
    bayes_result: BayesianResult | None = None

    # ── Distribution model ────────────────────────────────────────
    if len(historical_all) >= 8:
        dist_result = fit_distribution(historical_all, features.line)
        if dist_result:
            probs["distribution"] = dist_result.prob_over
            weights["distribution"] = _BASE_WEIGHTS["distribution"]
            if features.sample_size < 10:
                weights["distribution"] *= 0.5

    # ── Bayesian model ────────────────────────────────────────────
    if len(historical_all) >= 5 and len(historical_recent) >= 3:
        bayes_result = bayesian_prob_over(
            historical_all=historical_all,
            historical_recent=historical_recent,
            line=features.line,
            stat_is_continuous=is_continuous(features.stat_type),
        )
        if bayes_result:
            probs["bayesian"] = bayes_result.prob_over
            weights["bayesian"] = _BASE_WEIGHTS["bayesian"]
            if features.sample_size < 10:
                weights["bayesian"] *= 0.5

    # ── ML model ──────────────────────────────────────────────────
    if features.sample_size >= 15:
        ml_prob = ml_model.predict_prob_over(features)
        if ml_prob is not None:
            probs["ml"] = ml_prob
            weights["ml"] = _BASE_WEIGHTS["ml"]

    # ── Sharp line model ──────────────────────────────────────────
    if features.sharp_implied_prob is not None:
        probs["sharp"] = features.sharp_implied_prob
        weights["sharp"] = _BASE_WEIGHTS["sharp"]

    # ── If we have nothing, fall back to sharp or 0.50 ───────────
    if not probs:
        fallback = features.sharp_implied_prob or 0.50
        return EnsembleResult(
            final_prob_over=fallback,
            distribution_prob=None,
            bayesian_prob=None,
            ml_prob=None,
            sharp_prob=features.sharp_implied_prob,
            confidence=20.0,
            model_agreement=0.0,
            n_models=0,
            weights_used={},
            distribution_result=dist_result,
            bayesian_result=bayes_result,
        )

    # ── Weighted average ──────────────────────────────────────────
    total_weight = sum(weights[k] for k in probs)
    final_prob = sum(probs[k] * weights[k] for k in probs) / total_weight

    # Normalise used weights
    weights_used = {k: weights[k] / total_weight for k in probs}

    prob_values = list(probs.values())
    model_agreement = float(np.std(prob_values)) if len(prob_values) > 1 else 0.0

    # ── Confidence scoring ────────────────────────────────────────
    confidence = 50.0

    # Model agreement bonus
    if model_agreement < 0.03:
        confidence += 15
    elif model_agreement < 0.06:
        confidence += 8
    elif model_agreement > 0.12:
        confidence -= 10

    # Sharp book presence
    if features.sharp_implied_prob is not None:
        confidence += 10

    # Sample size
    if features.sample_size >= 20:
        confidence += 10
    elif features.sample_size < 10:
        confidence -= 15

    # Data quality
    if features.data_quality >= 0.8:
        confidence += 8
    elif features.data_quality < 0.4:
        confidence -= 10

    # Sharp deviation in same direction as edge
    if features.sharp_soft_deviation is not None:
        edge_dir = 1 if final_prob > 0.5 else -1
        dev_dir  = 1 if features.sharp_soft_deviation > 0 else -1
        if edge_dir == dev_dir and abs(features.sharp_soft_deviation) >= 0.02:
            confidence += 7

    # Number of models
    confidence += (len(probs) - 1) * 3

    confidence = float(np.clip(confidence, 0, 100))

    return EnsembleResult(
        final_prob_over=float(np.clip(final_prob, 0.01, 0.99)),
        distribution_prob=probs.get("distribution"),
        bayesian_prob=probs.get("bayesian"),
        ml_prob=probs.get("ml"),
        sharp_prob=probs.get("sharp"),
        confidence=confidence,
        model_agreement=model_agreement,
        n_models=len(probs),
        weights_used=weights_used,
        distribution_result=dist_result,
        bayesian_result=bayes_result,
    )
