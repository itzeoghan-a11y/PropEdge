"""
Steam Detection Engine.

Steam moves = rapid, coordinated line movement across multiple books
indicating sharp money on one side.

Algorithm
---------
For each prop, look at LineMovementEvents within the detection window:

1. Count books that moved in the same direction
2. Measure total line delta
3. Calculate velocity (delta / elapsed_minutes)
4. Cross-check: is public bet % moving AGAINST the line? → Reverse Line Movement

A steam alert is fired when:
  - >= 2 books moved in the same direction within the window
  - Total line delta >= 0.5
  - Velocity >= 0.5 points/min

Reverse Line Movement is flagged when:
  - Public bets heavily favor one side (would normally push the line that way)
  - But the line is moving opposite → sharps are on the other side
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import LineMovementEvent, SteamAlert
from app.models.prop import Prop

log = logging.getLogger(__name__)
settings = get_settings()


async def detect_steam(
    prop_id: int,
    db: AsyncSession,
    *,
    window_seconds: int | None = None,
) -> SteamAlert | None:
    """
    Check recent line movement events for a prop and emit a SteamAlert
    if steam is detected.

    Returns the SteamAlert if created, else None.
    """
    window = window_seconds or settings.steam_detection_window_seconds
    cutoff = datetime.utcnow() - timedelta(seconds=window)

    result = await db.execute(
        select(LineMovementEvent).where(
            and_(
                LineMovementEvent.prop_id == prop_id,
                LineMovementEvent.moved_at >= cutoff,
            )
        ).order_by(LineMovementEvent.moved_at.asc())
    )
    events: list[LineMovementEvent] = list(result.scalars().all())

    if len(events) < 2:
        return None

    # Separate by direction
    up_events   = [e for e in events if e.direction == "up"]
    down_events = [e for e in events if e.direction == "down"]

    for direction_label, direction_events in [("over", up_events), ("under", down_events)]:
        if len(direction_events) < 2:
            continue

        books_moved = list({e.bookmaker for e in direction_events})
        if len(books_moved) < 2:
            continue

        # Line delta: compare earliest to latest in this set
        earliest = direction_events[0]
        latest   = direction_events[-1]
        line_delta = abs(latest.line_after - earliest.line_before)

        if line_delta < 0.5:
            continue

        # Velocity (points per minute)
        elapsed_seconds = max(
            (latest.moved_at - earliest.moved_at).total_seconds(), 1.0
        )
        elapsed_minutes = elapsed_seconds / 60
        velocity = line_delta / elapsed_minutes

        if velocity < 0.5:
            continue

        # Check for duplicate alert in last 30 min
        recent_check = await db.execute(
            select(SteamAlert).where(
                and_(
                    SteamAlert.prop_id == prop_id,
                    SteamAlert.direction == direction_label,
                    SteamAlert.detected_at >= datetime.utcnow() - timedelta(minutes=30),
                )
            ).limit(1)
        )
        if recent_check.scalar_one_or_none():
            continue   # already alerted recently

        alert = SteamAlert(
            prop_id=prop_id,
            direction=direction_label,
            books_moved=books_moved,
            line_before=float(earliest.line_before),
            line_after=float(latest.line_after),
            line_delta=round(line_delta, 2),
            velocity=round(velocity, 3),
            window_seconds=window,
            is_reverse_line_movement=False,  # RLM requires public bet% data
        )
        db.add(alert)
        await db.flush()

        log.info(
            "Steam detected on prop %d (%s): %.2f pt move across %s in %.0fs",
            prop_id, direction_label, line_delta, books_moved, elapsed_seconds,
        )
        return alert

    return None


async def scan_all_props_for_steam(db: AsyncSession) -> int:
    """
    Scan all active props for steam.  Called periodically by Celery beat.
    Returns number of steam alerts fired.
    """
    result = await db.execute(
        select(Prop.id).where(Prop.is_active.is_(True))
    )
    prop_ids = list(result.scalars().all())

    alerts_fired = 0
    for prop_id in prop_ids:
        alert = await detect_steam(prop_id, db)
        if alert:
            alerts_fired += 1

    await db.commit()
    return alerts_fired
