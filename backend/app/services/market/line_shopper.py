"""
Line Shopping Service.

For each prop, compares odds across all available sportsbooks to:

1. Identify the BEST AVAILABLE LINE per direction
   - Best over  = highest decimal odds (most payout)
   - Best under = highest decimal odds (most payout)

2. Flag "soft" books relative to the sharp consensus
   A book is soft when its no-vig implied probability is meaningfully
   lower (more favorable to the bettor) than Pinnacle's no-vig line.
   Example: Pinnacle has LeBron points OVER 27.5 at 52% implied.
            DraftKings still has the OVER at 24.5 (45% implied).
            DK is soft — they haven't moved to match sharp action.

3. Calculate cross-book dispersion
   High dispersion = books disagree = opportunity for line shopping.

4. Update Prop with best available numbers for the dashboard.

Called from:
  - odds_collector.py after each collection batch (per prop)
  - ev_engine.py (passed result to mark is_best_available_line on EVOpportunity)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from app.models import OddsSnapshot

log = logging.getLogger(__name__)

# A book whose no-vig prob is this much lower than sharp is flagged "soft"
SOFT_THRESHOLD = 0.025   # 2.5 percentage points


def _no_vig_prob_over(snap: OddsSnapshot) -> float:
    """Remove vig from a two-sided market, return fair prob for over."""
    imp_over  = 1 / snap.odds_over  if snap.odds_over  > 1 else 0.5
    imp_under = 1 / snap.odds_under if snap.odds_under > 1 else 0.5
    total = imp_over + imp_under
    return imp_over / total if total > 0 else 0.5


@dataclass
class LineShoppingResult:
    prop_id: int

    # Best odds available (highest decimal = best payout) across soft books
    best_over_book: str | None = None
    best_over_odds: float | None = None      # decimal odds
    best_over_no_vig_prob: float | None = None

    best_under_book: str | None = None
    best_under_odds: float | None = None
    best_under_no_vig_prob: float | None = None

    # Sharp reference
    sharp_line: float | None = None
    sharp_no_vig_prob_over: float | None = None

    # Consensus (average of soft books, no-vig)
    consensus_no_vig_prob_over: float | None = None
    consensus_line: float | None = None      # weighted-avg line across soft books

    # Dispersion — how spread out are lines/probs across books?
    line_dispersion: float | None = None     # std of lines across soft books
    prob_dispersion: float | None = None     # std of no-vig probs across soft books

    # Soft books: those whose no-vig prob is notably below sharp
    soft_over_books: list[str] = field(default_factory=list)
    soft_under_books: list[str] = field(default_factory=list)

    # All book data for transparency
    book_details: list[dict] = field(default_factory=list)


def compute_line_shopping(
    prop_id: int,
    snapshots: list[OddsSnapshot],
    sharp_books: list[str],
) -> LineShoppingResult:
    """
    Core line shopping computation.

    Parameters
    ----------
    prop_id   : the prop being analysed
    snapshots : latest snapshot per bookmaker (caller ensures one per book)
    sharp_books : list of bookmaker keys treated as sharp reference
    """
    result = LineShoppingResult(prop_id=prop_id)

    if not snapshots:
        return result

    sharp_snaps = [s for s in snapshots if s.bookmaker in sharp_books]
    soft_snaps  = [s for s in snapshots if s.bookmaker not in sharp_books]

    # ── Sharp reference ───────────────────────────────────────────
    if sharp_snaps:
        # Use the sharpest available book (prefer Pinnacle)
        preferred = next(
            (s for s in sharp_snaps if s.bookmaker == "pinnacle"), sharp_snaps[0]
        )
        result.sharp_line = preferred.line
        result.sharp_no_vig_prob_over = _no_vig_prob_over(preferred)

    # ── Soft book analysis ────────────────────────────────────────
    if not soft_snaps:
        return result

    soft_probs_over: list[float] = []
    soft_lines: list[float] = []

    for snap in soft_snaps:
        nv_over = _no_vig_prob_over(snap)
        soft_probs_over.append(nv_over)
        soft_lines.append(snap.line)

        result.book_details.append({
            "bookmaker": snap.bookmaker,
            "line": snap.line,
            "odds_over": snap.odds_over,
            "odds_under": snap.odds_under,
            "no_vig_prob_over": round(nv_over, 4),
            "is_sharp": False,
        })

    # Add sharp book details too (for display)
    for snap in sharp_snaps:
        nv_over = _no_vig_prob_over(snap)
        result.book_details.append({
            "bookmaker": snap.bookmaker,
            "line": snap.line,
            "odds_over": snap.odds_over,
            "odds_under": snap.odds_under,
            "no_vig_prob_over": round(nv_over, 4),
            "is_sharp": True,
        })

    # Consensus
    if soft_probs_over:
        result.consensus_no_vig_prob_over = float(np.mean(soft_probs_over))
        result.consensus_line = float(np.mean(soft_lines))

    if len(soft_lines) > 1:
        result.line_dispersion = float(np.std(soft_lines))
        result.prob_dispersion = float(np.std(soft_probs_over))

    # ── Best available odds ───────────────────────────────────────
    # Best over  = highest decimal odds for the over outcome
    best_over_snap = max(soft_snaps, key=lambda s: s.odds_over)
    result.best_over_book = best_over_snap.bookmaker
    result.best_over_odds = best_over_snap.odds_over
    result.best_over_no_vig_prob = _no_vig_prob_over(best_over_snap)

    # Best under = highest decimal odds for the under outcome
    best_under_snap = max(soft_snaps, key=lambda s: s.odds_under)
    result.best_under_book = best_under_snap.bookmaker
    result.best_under_odds = best_under_snap.odds_under
    result.best_under_no_vig_prob = 1 - _no_vig_prob_over(best_under_snap)

    # ── Soft book detection ───────────────────────────────────────
    if result.sharp_no_vig_prob_over is not None:
        sharp_p = result.sharp_no_vig_prob_over
        for snap in soft_snaps:
            nv = _no_vig_prob_over(snap)
            # Over is soft when soft book's implied is LOWER than sharp
            # (book is offering a more favorable over price than sharp consensus)
            if sharp_p - nv >= SOFT_THRESHOLD:
                result.soft_over_books.append(snap.bookmaker)
            # Under is soft when soft book's implied is HIGHER than sharp
            # (book is offering a more favorable under price than sharp consensus)
            if nv - sharp_p >= SOFT_THRESHOLD:
                result.soft_under_books.append(snap.bookmaker)

    return result


def apply_line_shopping_to_prop(prop, result: LineShoppingResult) -> None:
    """Write line shopping summary back to a Prop ORM object."""
    prop.consensus_line    = result.consensus_line
    prop.line_dispersion   = result.line_dispersion
    prop.best_over_book    = result.best_over_book
    prop.best_over_odds    = result.best_over_odds
    prop.best_under_book   = result.best_under_book
    prop.best_under_odds   = result.best_under_odds
    prop.soft_book_count   = len(result.soft_over_books) + len(result.soft_under_books)
