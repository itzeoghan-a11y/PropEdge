from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.prop import Prop


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    team: Mapped[str] = mapped_column(String(64))
    team_abbr: Mapped[str] = mapped_column(String(8))
    position: Mapped[str] = mapped_column(String(16))
    jersey_number: Mapped[str | None] = mapped_column(String(4), nullable=True)
    injury_status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    game_logs: Mapped[list[PlayerGameLog]] = relationship(
        "PlayerGameLog", back_populates="player", cascade="all, delete-orphan"
    )
    props: Mapped[list[Prop]] = relationship("Prop", back_populates="player")


class PlayerGameLog(Base):
    __tablename__ = "player_game_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    game_date: Mapped[date] = mapped_column(Date, index=True)
    opponent_team: Mapped[str] = mapped_column(String(64))
    opponent_abbr: Mapped[str] = mapped_column(String(8))
    is_home: Mapped[bool] = mapped_column(default=True)
    result: Mapped[str | None] = mapped_column(String(4), nullable=True)  # W/L

    # Core playing time
    minutes_played: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Basketball
    points: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebounds: Mapped[float | None] = mapped_column(Float, nullable=True)
    assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    three_pointers_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    steals: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocks: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnovers: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    true_shooting_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Football
    passing_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    interceptions: Mapped[float | None] = mapped_column(Float, nullable=True)
    rushing_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    rushing_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    receiving_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    receptions: Mapped[float | None] = mapped_column(Float, nullable=True)
    receiving_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    targets: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Baseball
    hits: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_runs: Mapped[float | None] = mapped_column(Float, nullable=True)
    rbis: Mapped[float | None] = mapped_column(Float, nullable=True)
    strikeouts_pitcher: Mapped[float | None] = mapped_column(Float, nullable=True)
    earned_runs: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Hockey
    goals: Mapped[float | None] = mapped_column(Float, nullable=True)
    hockey_assists: Mapped[float | None] = mapped_column(Float, nullable=True)
    shots_on_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_minus: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Game context
    team_pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    opponent_def_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    opponent_pace: Mapped[float | None] = mapped_column(Float, nullable=True)
    days_rest: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    player: Mapped[Player] = relationship("Player", back_populates="game_logs")


class TeamDefenseRanking(Base):
    """Defensive rankings by team and stat type — updated nightly."""

    __tablename__ = "team_defense_rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport: Mapped[str] = mapped_column(String(32))
    season: Mapped[str] = mapped_column(String(12))
    team_abbr: Mapped[str] = mapped_column(String(8))
    stat_type: Mapped[str] = mapped_column(String(64))   # "points", "rebounds", etc.
    avg_allowed: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)            # 1 = best defense
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
