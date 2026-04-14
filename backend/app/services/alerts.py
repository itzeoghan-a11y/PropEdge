"""
Alert dispatch service.

Sends notifications via Discord webhook and/or email for:
  - New EV opportunities (by tier)
  - Steam moves
  - Elite/high edge props
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import EVOpportunity, Player, Prop, SteamAlert, User

log = logging.getLogger(__name__)
settings = get_settings()


async def _post_discord(webhook_url: str, content: str) -> None:
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                webhook_url,
                json={"content": content[:2000]},
                timeout=10.0,
            )
    except Exception as exc:
        log.warning("Discord alert failed: %s", exc)


def _ev_tier_emoji(tier: str) -> str:
    return {"elite": "🔥🔥🔥", "high": "⚡⚡", "standard": "✅"}.get(tier, "")


async def dispatch_pending_alerts(db: AsyncSession) -> int:
    """Send alerts for all un-alerted EV opportunities. Returns count sent."""
    result = await db.execute(
        select(EVOpportunity, Prop, Player)
        .join(Prop, EVOpportunity.prop_id == Prop.id)
        .join(Player, Prop.player_id == Player.id)
        .where(EVOpportunity.is_alerted.is_(False))
        .order_by(EVOpportunity.found_at.asc())
        .limit(50)
    )
    rows = result.all()

    if not rows:
        return 0

    # Build alert messages
    messages: list[str] = []
    for opp, prop, player in rows:
        direction_str = "OVER" if opp.direction == "over" else "UNDER"
        msg = (
            f"{_ev_tier_emoji(opp.tier)} **{player.name}** {prop.stat_type.upper()} "
            f"{direction_str} {prop.line} @ **{opp.bookmaker.upper()}**\n"
            f"Odds: `{opp.book_odds:.3f}` | Model: `{opp.model_prob*100:.1f}%` | "
            f"Implied: `{opp.implied_prob*100:.1f}%` | Edge: `+{opp.edge*100:.2f}%` | "
            f"EV: `{opp.ev*100:.2f}%` | Conf: `{opp.confidence_score:.0f}/100`"
        )
        messages.append(msg)
        opp.is_alerted = True

    # Send to platform Discord (operator webhook)
    if settings.discord_webhook_url and messages:
        batch = "\n\n".join(messages[:10])
        await _post_discord(
            settings.discord_webhook_url,
            f"**PropEdge Pro — {len(messages)} new EV prop(s)**\n\n{batch}",
        )

    # Send per-user alerts (Elite tier)
    users_result = await db.execute(
        select(User).where(
            and_(User.tier.in_(["pro", "elite"]), User.discord_webhook.is_not(None))
        )
    )
    users = users_result.scalars().all()

    for user in users:
        # Filter to user's thresholds
        user_opps = [
            (opp, prop, player) for opp, prop, player in rows
            if opp.ev >= user.alert_min_ev
            and opp.confidence_score >= user.alert_min_confidence
        ]
        if not user_opps:
            continue

        user_msgs = []
        for opp, prop, player in user_opps[:5]:
            direction_str = "OVER" if opp.direction == "over" else "UNDER"
            user_msgs.append(
                f"{_ev_tier_emoji(opp.tier)} **{player.name}** "
                f"{prop.stat_type.upper()} {direction_str} {prop.line} "
                f"@ {opp.bookmaker.upper()} | Edge +{opp.edge*100:.2f}%"
            )

        await _post_discord(
            user.discord_webhook,
            "**PropEdge Pro — Your EV Alerts**\n\n" + "\n".join(user_msgs),
        )

    await db.flush()
    return len(rows)


async def dispatch_steam_alert(steam: SteamAlert, db: AsyncSession) -> None:
    """Send a steam move alert to the platform Discord."""
    prop_result = await db.execute(
        select(Prop, Player)
        .join(Player, Prop.player_id == Player.id)
        .where(Prop.id == steam.prop_id)
    )
    row = prop_result.first()
    if not row:
        return

    prop, player = row
    msg = (
        f"⚡ **STEAM MOVE** — {player.name} {prop.stat_type.upper()} "
        f"{steam.direction.upper()}\n"
        f"Line moved {steam.line_before} → {steam.line_after} "
        f"({steam.line_delta:+.1f} pts) | "
        f"Velocity: {steam.velocity:.2f} pts/min\n"
        f"Books: {', '.join(steam.books_moved)}"
    )
    await _post_discord(settings.discord_webhook_url, msg)

    # Alert Elite users who opted into steam
    users_result = await db.execute(
        select(User).where(
            and_(User.tier == "elite", User.alert_steam.is_(True), User.discord_webhook.is_not(None))
        )
    )
    for user in users_result.scalars().all():
        await _post_discord(user.discord_webhook, msg)
