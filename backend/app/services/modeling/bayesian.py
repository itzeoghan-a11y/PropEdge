"""
Bayesian Model.

Uses conjugate prior updates to produce a posterior P(stat > line).

Approach
--------
For count stats (points, rebounds, etc.):
  Prior: Gamma(α, β) conjugate to Poisson likelihood.
  Prior α, β derived from historical season average.
  Observation: last N games (weighted by recency).
  Posterior predictive: Negative Binomial.

The recency weighting means sharp recent slumps/surges pull the posterior
more strongly than older games — capturing form.

For continuous stats (passing yards, etc.):
  Normal-Normal conjugate update.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy import stats

log = logging.getLogger(__name__)

# Recency weights: index 0 = most recent, index -1 = oldest
_RECENCY_WEIGHTS = np.array([4.0, 3.0, 2.5, 2.0, 1.5, 1.2, 1.0, 0.9, 0.8, 0.7])


@dataclass
class BayesianResult:
    prob_over: float
    posterior_mean: float
    posterior_std: float
    prior_mean: float
    n_observations: int
    update_strength: float   # 0–1; how much the data shifted the prior


def _gamma_poisson_update(
    prior_mu: float,
    observations: list[float],
    recency_weights: np.ndarray,
) -> tuple[float, float]:
    """
    Gamma-Poisson conjugate update.

    Prior: Gamma(alpha_0, beta_0) where prior_mu = alpha_0 / beta_0.
    Posterior: Gamma(alpha_0 + sum(obs), beta_0 + n_effective).

    Returns (posterior_alpha, posterior_beta).
    """
    # Set prior with moderate confidence (beta_0 = 5 gives ~5 pseudo-observations)
    beta_0 = 5.0
    alpha_0 = prior_mu * beta_0

    # Weight observations by recency
    n = min(len(observations), len(recency_weights))
    weights = recency_weights[:n]
    weights = weights / weights.sum()

    obs_arr = np.array(observations[-n:])

    # Effective observations (fractional due to weighting)
    effective_sum = float(np.dot(obs_arr, weights) * n)
    n_effective = float(weights.sum() * n)

    alpha_post = alpha_0 + effective_sum
    beta_post  = beta_0  + n_effective

    return alpha_post, beta_post


def _negbin_sf(k: float, r: float, p: float) -> float:
    """P(X > k) for Negative Binomial (r, p)."""
    return float(stats.nbinom.sf(int(k), r, p))


def _normal_update(
    prior_mu: float,
    prior_std: float,
    observations: list[float],
    obs_std: float,
) -> tuple[float, float]:
    """
    Normal-Normal conjugate update.
    Returns (posterior_mean, posterior_std).
    """
    n = len(observations)
    obs_mean = float(np.mean(observations))

    # Posterior precision = prior precision + n * likelihood precision
    prior_prec = 1 / (prior_std ** 2 + 1e-9)
    lik_prec   = n / (obs_std ** 2 + 1e-9)

    post_prec = prior_prec + lik_prec
    post_mu   = (prior_prec * prior_mu + lik_prec * obs_mean) / post_prec
    post_std  = (1 / post_prec) ** 0.5

    return post_mu, post_std


def bayesian_prob_over(
    historical_all: list[float],   # full season (for prior)
    historical_recent: list[float], # last ~10 games (for update)
    line: float,
    stat_is_continuous: bool = False,
) -> BayesianResult | None:
    """
    Compute Bayesian posterior P(stat > line).

    Parameters
    ----------
    historical_all    : full season values (used to compute prior)
    historical_recent : recent N games (used to update prior)
    line              : the over/under line to evaluate
    stat_is_continuous: use Normal-Normal if True, Gamma-Poisson if False
    """
    if len(historical_all) < 5 or len(historical_recent) < 3:
        return None

    prior_mu  = float(np.mean(historical_all))
    prior_std = float(np.std(historical_all, ddof=1)) + 1e-3

    n_recent = len(historical_recent)

    if stat_is_continuous:
        # Normal-Normal update
        post_mu, post_std = _normal_update(
            prior_mu, prior_std, historical_recent, obs_std=prior_std
        )
        prob_over = float(stats.norm.sf(line, loc=post_mu, scale=post_std))
        posterior_std = post_std

        update_strength = min(
            abs(post_mu - prior_mu) / (prior_std + 1e-9), 1.0
        )

    else:
        # Gamma-Poisson update → Negative Binomial predictive
        weights = _RECENCY_WEIGHTS[:n_recent]
        alpha_post, beta_post = _gamma_poisson_update(
            prior_mu, historical_recent, weights
        )
        # NegBin predictive: r = alpha_post, p = beta_post / (beta_post + 1)
        r = alpha_post
        p = beta_post / (beta_post + 1)
        prob_over = _negbin_sf(line, r, p)

        post_mu  = alpha_post / beta_post
        posterior_std = float(np.sqrt(alpha_post * (beta_post + 1) / beta_post**2))

        update_strength = min(
            abs(post_mu - prior_mu) / (prior_std + 1e-9), 1.0
        )

    return BayesianResult(
        prob_over=float(np.clip(prob_over, 0.01, 0.99)),
        posterior_mean=post_mu,
        posterior_std=posterior_std,
        prior_mean=prior_mu,
        n_observations=n_recent,
        update_strength=update_strength,
    )


CONTINUOUS_STATS: frozenset[str] = frozenset({
    "passing_yards",
    "rushing_yards",
    "receiving_yards",
    "passing_touchdowns",
})


def is_continuous(stat_type: str) -> bool:
    return stat_type in CONTINUOUS_STATS
