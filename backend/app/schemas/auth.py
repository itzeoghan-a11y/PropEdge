from __future__ import annotations

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str | None = None


class UserLogin(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None
    tier: str
    subscription_status: str
    has_active_subscription: bool
    daily_prop_limit: int | None
    alert_min_ev: float
    alert_min_confidence: float
    alert_steam: bool

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    discord_webhook: str | None = None
    phone_number: str | None = None
    alert_min_ev: float | None = None
    alert_min_confidence: float | None = None
    alert_steam: bool | None = None


class StripeCheckoutOut(BaseModel):
    checkout_url: str
