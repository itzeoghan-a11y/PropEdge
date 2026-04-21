from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_list(v: object, default: list[str]) -> list[str]:
    if v is None or v == "":
        return default
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        v = v.strip()
        if v.startswith("["):
            return json.loads(v)
        return [x.strip() for x in v.split(",") if x.strip()]
    return default


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        extra="ignore",
        # Disable automatic JSON parsing for list fields so our validators run
        json_schema_extra={},
    )

    # ── App ────────────────────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"   # stored as str, parsed in property

    # ── Database ───────────────────────────────────────────────────
    database_url: str = Field("sqlite+aiosqlite:///./propedge.db", alias="DATABASE_URL")

    @property
    def async_database_url(self) -> str:
        """Convert postgres:// or postgresql:// to postgresql+asyncpg:// for SQLAlchemy async.

        asyncpg rejects libpq-style query params (sslmode, channel_binding), so
        strip them here — Railway/Heroku Postgres URLs both include sslmode=require.
        TLS is still negotiated automatically by asyncpg when the server requests it.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        if "+asyncpg" in url and ("?" in url):
            parts = urlsplit(url)
            drop = {"sslmode", "channel_binding", "gssencmode", "target_session_attrs"}
            kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                    if k not in drop]
            url = urlunsplit((parts.scheme, parts.netloc, parts.path,
                              urlencode(kept), parts.fragment))
        return url

    # ── Redis / Celery ─────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # ── Auth ───────────────────────────────────────────────────────
    secret_key: str = Field("changeme_in_production", alias="SECRET_KEY")
    access_token_expire_minutes: int = 1440

    # ── Stripe ─────────────────────────────────────────────────────
    stripe_secret_key: str = Field("", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field("", alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_pro: str = Field("", alias="STRIPE_PRICE_PRO")
    stripe_price_elite: str = Field("", alias="STRIPE_PRICE_ELITE")

    # ── External APIs ──────────────────────────────────────────────
    odds_api_key: str = Field("", alias="ODDS_API_KEY")
    odds_api_base: str = "https://api.the-odds-api.com/v4"
    sports_data_api_key: str = Field("", alias="SPORTS_DATA_API_KEY")

    # ── Alert Channels ─────────────────────────────────────────────
    discord_webhook_url: str = Field("", alias="DISCORD_WEBHOOK_URL")
    sendgrid_api_key: str = Field("", alias="SENDGRID_API_KEY")
    twilio_account_sid: str = Field("", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field("", alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: str = Field("", alias="TWILIO_FROM_NUMBER")

    # ── Feature Flags / Thresholds ─────────────────────────────────
    enable_ml_model: bool = False
    odds_poll_interval: int = 30
    steam_detection_window_seconds: int = 300
    min_ev_threshold: float = 0.03
    min_confidence_threshold: float = 50.0

    # Lists stored as comma-separated strings in .env
    _active_sports_str: str = "basketball_nba,americanfootball_nfl,baseball_mlb,icehockey_nhl"
    _sharp_books_str: str = "pinnacle,betfair,matchbook"
    _soft_books_str: str = "draftkings,fanduel,betmgm,caesars,pointsbetus"

    @property
    def cors_origins_list(self) -> list[str]:
        return _parse_list(self.cors_origins, ["http://localhost:3000"])

    @property
    def active_sports(self) -> list[str]:
        return ["basketball_nba", "americanfootball_nfl", "baseball_mlb", "icehockey_nhl"]

    @property
    def sharp_books(self) -> list[str]:
        return ["pinnacle", "betfair", "matchbook"]

    @property
    def soft_books(self) -> list[str]:
        return ["draftkings", "fanduel", "betmgm", "caesars", "pointsbetus"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
