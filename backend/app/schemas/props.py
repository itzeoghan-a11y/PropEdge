from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class OddsOut(BaseModel):
    bookmaker: str
    line: float
    odds_over: float
    odds_under: float
    implied_prob_over: float
    is_sharp: bool
    recorded_at: datetime


class EVOpportunityOut(BaseModel):
    id: int
    direction: Literal["over", "under"]
    bookmaker: str
    book_odds: float
    implied_prob: float
    model_prob: float
    edge: float
    ev: float
    confidence_score: float
    tier: Literal["standard", "high", "elite"]
    sharp_prob: float | None
    sharp_deviation: float | None
    is_best_available_line: bool
    steam_boosted: bool
    line_at_flag: float | None
    found_at: datetime


class ModelBreakdownOut(BaseModel):
    distribution_prob: float | None
    bayesian_prob: float | None
    ml_prob: float | None
    sharp_prob: float | None
    final_prob_over: float
    confidence: float
    model_agreement: float
    n_models: int
    weights_used: dict[str, float]


class SteamAlertOut(BaseModel):
    id: int
    direction: str
    books_moved: list[str]
    line_before: float
    line_after: float
    line_delta: float
    velocity: float
    detected_at: datetime


class BookDetailOut(BaseModel):
    """Single book's line/odds for line shopping view."""
    bookmaker: str
    line: float
    odds_over: float
    odds_under: float
    no_vig_prob_over: float
    is_sharp: bool


class LineShopping(BaseModel):
    """Cross-book line shopping data for a prop."""
    best_over_book: str | None
    best_over_odds: float | None
    best_under_book: str | None
    best_under_odds: float | None
    sharp_line: float | None
    sharp_no_vig_prob_over: float | None
    consensus_line: float | None
    consensus_no_vig_prob_over: float | None
    line_dispersion: float | None
    prob_dispersion: float | None
    soft_over_books: list[str]
    soft_under_books: list[str]
    book_details: list[BookDetailOut]


class PropSummaryOut(BaseModel):
    """Compact row for the dashboard table."""
    id: int
    player_id: int
    player_name: str
    sport: str
    stat_type: str
    line: float
    game_date: date
    opponent_team: str

    # Best EV opportunity fields
    best_direction: str | None
    best_bookmaker: str | None
    best_book_odds: float | None
    model_prob: float | None
    implied_prob: float | None
    edge: float | None
    ev: float | None
    confidence: float | None
    tier: str | None
    sharp_prob: float | None

    # Line shopping summary
    best_over_book: str | None
    best_over_odds: float | None
    best_under_book: str | None
    best_under_odds: float | None
    consensus_line: float | None
    line_dispersion: float | None
    soft_book_count: int | None

    has_steam: bool
    steam_boosted: bool
    is_overdue: bool

    class Config:
        from_attributes = True


class PropDetailOut(BaseModel):
    """Full prop detail for the prop page."""
    id: int
    player_id: int
    player_name: str
    sport: str
    stat_type: str
    line: float
    game_date: date
    opponent_team: str

    ev_opportunities: list[EVOpportunityOut]
    model_breakdown: ModelBreakdownOut | None
    latest_odds: list[OddsOut]
    steam_alerts: list[SteamAlertOut]
    line_shopping: LineShopping | None

    # Feature snapshot (for "why this bet?" panel)
    rolling_avg_5: float | None
    rolling_avg_10: float | None
    rolling_std_10: float | None
    hit_rate_line: float | None
    opp_def_rank_pct: float | None
    sharp_soft_deviation: float | None
    sample_size: int

    class Config:
        from_attributes = True


class PropFilter(BaseModel):
    sport: str | None = None
    stat_type: str | None = None
    min_ev: float = Field(default=0.03, ge=0.0, le=1.0)
    min_confidence: float = Field(default=50.0, ge=0.0, le=100.0)
    bookmaker: str | None = None
    tier: str | None = None
    direction: str | None = None
    game_date: date | None = None
    best_available_only: bool = False    # filter to is_best_available_line=True rows
    has_steam: bool | None = None        # filter to props with active steam
