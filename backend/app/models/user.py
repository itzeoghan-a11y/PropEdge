from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

Tier = Literal["free", "pro", "elite"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tier: Mapped[str] = mapped_column(String(16), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stripe
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(32), default="inactive")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Preferences
    discord_webhook: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    alert_min_ev: Mapped[float] = mapped_column(default=0.05)
    alert_min_confidence: Mapped[float] = mapped_column(default=60.0)
    alert_steam: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def has_active_subscription(self) -> bool:
        if self.tier == "free":
            return True
        if self.current_period_end is None:
            return False
        return (
            self.subscription_status in ("active", "trialing")
            and datetime.utcnow() < self.current_period_end
        )

    @property
    def daily_prop_limit(self) -> int | None:
        """None = unlimited."""
        return {"free": 5, "pro": None, "elite": None}.get(self.tier, 5)
