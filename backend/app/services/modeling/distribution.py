"""
Distribution Model.

Fits the best statistical distribution to a player's historical outputs for
a given stat and returns P(stat > line).

Distribution selection priority
--------------------------------
1. Negative Binomial  — overdispersed count data (most basketball/football props)
2. Poisson            — low-variance count data (goals, home runs)
3. Normal             — continuous / high-volume stats (passing yards)

Goodness-of-fit is evaluated via AIC.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar
from scipy.special import gammaln

log = logging.getLogger(__name__)


@dataclass
class DistributionResult:
    model: str
    prob_over: float          # P(X > line)
    mean: float
    std: float
    fit_quality: float        # lower AIC is better; normalized to 0-1 across models
    params: dict


def _negbin_fit(data: np.ndarray) -> tuple[float, float]:
    """Fit Negative Binomial via MLE. Returns (r, p) params."""
    mu = data.mean()
    var = data.var()
    if var <= mu:
        var = mu + 1e-3   # fall back to Poisson-like

    r = mu**2 / (var - mu)
    p = r / (r + mu)
    return r, p


def _negbin_pmf(k: np.ndarray, r: float, p: float) -> np.ndarray:
    log_pmf = (
        gammaln(r + k) - gammaln(r) - gammaln(k + 1)
        + r * np.log(p)
        + k * np.log(1 - p)
    )
    return np.exp(log_pmf)


def _negbin_prob_over(line: float, r: float, p: float) -> float:
    """P(X > line) for NegBinomial(r, p)."""
    k = np.arange(0, int(line) + 1)
    pmf_vals = _negbin_pmf(k, r, p)
    return float(1.0 - pmf_vals.sum())


def _poisson_prob_over(line: float, mu: float) -> float:
    return float(1 - stats.poisson.cdf(int(line), mu))


def _normal_prob_over(line: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        sigma = 0.1
    return float(1 - stats.norm.cdf(line, loc=mu, scale=sigma))


def _aic(log_likelihood: float, n_params: int) -> float:
    return 2 * n_params - 2 * log_likelihood


def fit_distribution(
    historical: list[float],
    line: float,
    *,
    min_samples: int = 8,
) -> DistributionResult | None:
    """
    Fit the best distribution to historical stat values and return
    P(stat > line).

    Returns None if there is insufficient data.
    """
    data = np.array(historical, dtype=float)
    n = len(data)

    if n < min_samples:
        log.debug("Insufficient samples (%d < %d) for distribution fit", n, min_samples)
        return None

    mu = data.mean()
    sigma = data.std(ddof=1) if n > 1 else 1.0

    results: list[tuple[float, DistributionResult]] = []

    # ── Normal ─────────────────────────────────────────────────────
    try:
        ll_normal = np.sum(stats.norm.logpdf(data, loc=mu, scale=max(sigma, 0.1)))
        aic_normal = _aic(ll_normal, 2)
        p_normal = _normal_prob_over(line, mu, sigma)
        results.append((aic_normal, DistributionResult(
            model="normal",
            prob_over=p_normal,
            mean=mu,
            std=sigma,
            fit_quality=0.0,
            params={"mu": mu, "sigma": sigma},
        )))
    except Exception as exc:
        log.debug("Normal fit failed: %s", exc)

    # ── Poisson (only for non-negative integer-ish data) ───────────
    if data.min() >= 0 and mu > 0 and (data - data.astype(int)).mean() < 0.15:
        try:
            ll_poisson = np.sum(stats.poisson.logpmf(data.astype(int), mu=mu))
            aic_poisson = _aic(ll_poisson, 1)
            p_poisson = _poisson_prob_over(line, mu)
            results.append((aic_poisson, DistributionResult(
                model="poisson",
                prob_over=p_poisson,
                mean=mu,
                std=np.sqrt(mu),
                fit_quality=0.0,
                params={"mu": mu},
            )))
        except Exception as exc:
            log.debug("Poisson fit failed: %s", exc)

    # ── Negative Binomial ──────────────────────────────────────────
    if data.min() >= 0 and mu > 0 and sigma > 0:
        try:
            r, p = _negbin_fit(data)
            if r > 0 and 0 < p < 1:
                ll_nb = float(np.sum(np.log(_negbin_pmf(data.astype(int), r, p) + 1e-300)))
                aic_nb = _aic(ll_nb, 2)
                p_nb = _negbin_prob_over(line, r, p)
                results.append((aic_nb, DistributionResult(
                    model="negative_binomial",
                    prob_over=p_nb,
                    mean=mu,
                    std=sigma,
                    fit_quality=0.0,
                    params={"r": r, "p": p},
                )))
        except Exception as exc:
            log.debug("NegBin fit failed: %s", exc)

    if not results:
        return None

    # Select lowest AIC — best fit
    aic_vals = [r[0] for r in results]
    best_idx = int(np.argmin(aic_vals))
    winner = results[best_idx][1]

    # Normalize fit quality: 1.0 = this model has lowest AIC among candidates
    aic_range = max(aic_vals) - min(aic_vals) + 1e-9
    winner.fit_quality = 1.0 - (aic_vals[best_idx] - min(aic_vals)) / aic_range

    return winner
