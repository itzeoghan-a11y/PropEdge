from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.prop import Prop


class OddsSnapshot(Base):
    """
    Timestamped odds reading for a prop from one bookmaker.
    Immutable once written — forms the basis of line movement detection.
    """

    __tablename__ = "odds_snapshots"
    __table_args__ = (
        Index("ix_odds_prop_book_time", "prop_id", "bookmaker", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("props.id", ondelete="CASCADE"), index=True
    )
    bookmaker: Mapped[str] = mapped_column(String(32), index=True)
    line: Mapped[float] = mapped_column(Float)         # the prop number (e.g. 24.5)
    odds_over: Mapped[float] = mapped_column(Float)    # decimal
    odds_under: Mapped[float] = mapped_column(Float)   # decimal
    is_sharp: Mapped[bool] = mapped_column(default=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    prop: Mapped[Prop] = relationship("Prop", back_populates="odds_snapshots")

    @property
    def implied_prob_over(self) -> float:
        return 1 / self.odds_over if self.odds_over > 0 else 0.5

    @property
    def implied_prob_under(self) -> float:
        return 1 / self.odds_under if self.odds_under > 0 else 0.5

    @property
    def vig(self) -> float:
        """Overround — how much the book takes. 1.0 = no vig."""
        return self.implied_prob_over + self.implied_prob_under


class LineMovementEvent(Base):
    """
    Recorded whenever a bookmaker changes a line or odds.
    Used to construct line movement charts and detect steam.
    """

    __tablename__ = "line_movement_events"
    __table_args__ = (Index("ix_lme_prop_book_moved", "prop_id", "bookmaker", "moved_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("props.id", ondelete="CASCADE"), index=True
    )
    bookmaker: Mapped[str] = mapped_column(String(32))
    line_before: Mapped[float] = mapped_column(Float)
    line_after: Mapped[float] = mapped_column(Float)
    odds_over_before: Mapped[float] = mapped_column(Float)
    odds_over_after: Mapped[float] = mapped_column(Float)
    odds_under_before: Mapped[float] = mapped_column(Float)
    odds_under_after: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(8))   # "up" | "down"
    moved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
