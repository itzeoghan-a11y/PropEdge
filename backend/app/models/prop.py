from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.odds import OddsSnapshot


class Prop(Base):
    """A single player prop market for a specific game."""

    __tablename__ = "props"
    __table_args__ = (
        Index("ix_props_player_stat_game", "player_id", "stat_type", "game_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    stat_type: Mapped[str] = mapped_column(String(64), index=True)  # "points", "rebounds"
    line: Mapped[float] = mapped_column(Float)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    opponent_team: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    actual_result: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    player: Mapped[Player] = relationship("Player", back_populates="props")
    odds_snapshots: Mapped[list[OddsSnapshot]] = relationship(
        "OddsSnapshot", back_populates="prop", cascade="all, delete-orphan"
    )
    model_predictions: Mapped[list[ModelPrediction]] = relationship(
        "ModelPrediction", back_populates="prop", cascade="all, delete-orphan"
    )
    ev_opportunities: Mapped[list[EVOpportunity]] = relationship(
        "EVOpportunity", back_populates="prop", cascade="all, delete-orphan"
    )
    steam_alerts: Mapped[list[SteamAlert]] = relationship(
        "SteamAlert", back_populates="prop", cascade="all, delete-orphan"
    )


class ModelPrediction(Base):
    """Output of one model run for a given prop."""

    __tablename__ = "model_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("props.id", ondelete="CASCADE"), index=True
    )
    model_type: Mapped[str] = mapped_column(String(32))  # distribution|bayesian|ml|sharp|ensemble
    predicted_prob_over: Mapped[float] = mapped_column(Float)   # 0–1
    confidence: Mapped[float] = mapped_column(Float)            # 0–100
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)  # input features snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    prop: Mapped[Prop] = relationship("Prop", back_populates="model_predictions")


class EVOpportunity(Base):
    """
    A flagged +EV bet — persisted for alerting, history, and backtesting.
    """

    __tablename__ = "ev_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("props.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(8))   # "over" | "under"
    bookmaker: Mapped[str] = mapped_column(String(32))
    book_odds: Mapped[float] = mapped_column(Float)      # decimal
    implied_prob: Mapped[float] = mapped_column(Float)   # 0–1
    model_prob: Mapped[float] = mapped_column(Float)     # 0–1 ensemble
    edge: Mapped[float] = mapped_column(Float)           # model_prob - implied_prob
    ev: Mapped[float] = mapped_column(Float)             # expected value per unit
    confidence_score: Mapped[float] = mapped_column(Float)  # 0–100
    tier: Mapped[str] = mapped_column(String(16))        # "standard"|"high"|"elite"
    sharp_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharp_deviation: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    found_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    prop: Mapped[Prop] = relationship("Prop", back_populates="ev_opportunities")


class SteamAlert(Base):
    """Rapid line movement detected across books — steam move signal."""

    __tablename__ = "steam_alerts"
    __table_args__ = (Index("ix_steam_alerts_detected_at", "detected_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("props.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(8))    # "over" | "under"
    books_moved: Mapped[list[str]] = mapped_column(JSON) # bookmakers that moved
    line_before: Mapped[float] = mapped_column(Float)
    line_after: Mapped[float] = mapped_column(Float)
    line_delta: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float)       # points per minute
    window_seconds: Mapped[int] = mapped_column(Integer)
    is_reverse_line_movement: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    prop: Mapped[Prop] = relationship("Prop", back_populates="steam_alerts")


class BacktestResult(Base):
    """Aggregated backtest results for a model configuration."""

    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_label: Mapped[str] = mapped_column(String(128))
    sport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stat_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    total_bets: Mapped[int] = mapped_column(Integer)
    win_rate: Mapped[float] = mapped_column(Float)
    roi: Mapped[float] = mapped_column(Float)
    avg_ev: Mapped[float] = mapped_column(Float)
    avg_confidence: Mapped[float] = mapped_column(Float)
    calibration_error: Mapped[float] = mapped_column(Float)  # Brier score
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
