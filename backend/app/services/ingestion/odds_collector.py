"""
Odds ingestion service.

Pulls player prop odds from The Odds API (v4) for all configured sports,
writes OddsSnapshot rows, and fires LineMovementEvent records whenever
a line or odds shift is detected.

Sharp books (Pinnacle) are tagged and treated as the reference signal.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models import (
    LineMovementEvent,
    OddsSnapshot,
    Player,
    Prop,
)

log = logging.getLogger(__name__)
settings = get_settings()

PROP_MARKET_MAP: dict[str, list[str]] = {
    "basketball_nba": [
        "player_points",
        "player_rebounds",
        "player_assists",
        "player_threes",
        "player_blocks",
        "player_steals",
    ],
    "americanfootball_nfl": [
        "player_pass_yds",
        "player_rush_yds",
        "player_reception_yds",
        "player_receptions",
        "player_pass_tds",
        "player_rush_tds",
        "player_reception_tds",
    ],
    "baseball_mlb": [
        "batter_hits",
        "batter_home_runs",
        "batter_rbis",
        "pitcher_strikeouts",
    ],
    "icehockey_nhl": [
        "player_points",
        "player_shots_on_goal",
        "player_goals",
    ],
}

STAT_TYPE_MAP: dict[str, str] = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "three_pointers_made",
    "player_blocks": "blocks",
    "player_steals": "steals",
    "player_pass_yds": "passing_yards",
    "player_rush_yds": "rushing_yards",
    "player_reception_yds": "receiving_yards",
    "player_receptions": "receptions",
    "player_pass_tds": "passing_touchdowns",
    "player_rush_tds": "rushing_touchdowns",
    "player_reception_tds": "receiving_touchdowns",
    "batter_hits": "hits",
    "batter_home_runs": "home_runs",
    "batter_rbis": "rbis",
    "pitcher_strikeouts": "strikeouts_pitcher",
    "player_shots_on_goal": "shots_on_goal",
    "player_goals": "goals",
}


class OddsCollector:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._last_snapshots: dict[tuple[int, str], OddsSnapshot] = {}

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _get(self, url: str, params: dict[str, Any]) -> Any:
        response = await self._client.get(url, params=params, timeout=20.0)
        remaining = response.headers.get("x-requests-remaining", "?")
        log.debug("Odds API quota remaining: %s", remaining)
        response.raise_for_status()
        return response.json()

    async def collect_sport(self, sport: str, db: AsyncSession) -> int:
        """Fetch all prop markets for one sport. Returns # of snapshots written."""
        markets = PROP_MARKET_MAP.get(sport, [])
        if not markets:
            return 0

        all_books = settings.sharp_books + settings.soft_books
        written = 0

        for market_key in markets:
            try:
                data = await self._get(
                    f"{settings.odds_api_base}/sports/{sport}/odds",
                    params={
                        "apiKey": settings.odds_api_key,
                        "regions": "us",
                        "markets": market_key,
                        "oddsFormat": "decimal",
                        "bookmakers": ",".join(all_books),
                    },
                )
                written += await self._process_events(data, sport, market_key, db)
                await asyncio.sleep(0.5)   # gentle rate limiting
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 422:
                    log.debug("Market %s not available for %s", market_key, sport)
                else:
                    log.warning("HTTP error fetching %s/%s: %s", sport, market_key, exc)
            except Exception as exc:
                log.error("Error fetching %s/%s: %s", sport, market_key, exc)

        return written

    async def collect_all(self, db: AsyncSession) -> int:
        total = 0
        for sport in settings.active_sports:
            total += await self.collect_sport(sport, db)
        return total

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _process_events(
        self,
        events: list[dict],
        sport: str,
        market_key: str,
        db: AsyncSession,
    ) -> int:
        written = 0
        stat_type = STAT_TYPE_MAP.get(market_key, market_key)

        for event in events:
            game_date_str = event.get("commence_time", "")
            try:
                game_date = datetime.fromisoformat(
                    game_date_str.replace("Z", "+00:00")
                ).date()
            except (ValueError, AttributeError):
                continue

            for bookmaker in event.get("bookmakers", []):
                book_key = bookmaker["key"]
                is_sharp = book_key in settings.sharp_books

                for market in bookmaker.get("markets", []):
                    if market.get("key") != market_key:
                        continue

                    outcomes = market.get("outcomes", [])
                    over_outcome = next(
                        (o for o in outcomes if o.get("name") == "Over"), None
                    )
                    under_outcome = next(
                        (o for o in outcomes if o.get("name") == "Under"), None
                    )

                    if not over_outcome or not under_outcome:
                        continue

                    player_name = over_outcome.get("description", "")
                    if not player_name:
                        continue

                    line = float(over_outcome.get("point", 0))
                    odds_over = float(over_outcome.get("price", 1.91))
                    odds_under = float(under_outcome.get("price", 1.91))

                    # Resolve player
                    player = await self._get_or_create_player(
                        player_name, sport, db
                    )

                    # Resolve prop
                    prop = await self._get_or_create_prop(
                        player, sport, stat_type, line, game_date,
                        event.get("away_team", ""), db
                    )

                    # Write snapshot
                    snapshot = OddsSnapshot(
                        prop_id=prop.id,
                        bookmaker=book_key,
                        line=line,
                        odds_over=odds_over,
                        odds_under=odds_under,
                        is_sharp=is_sharp,
                    )
                    db.add(snapshot)

                    # Detect line movement
                    cache_key = (prop.id, book_key)
                    last = self._last_snapshots.get(cache_key)
                    if last and (
                        abs(last.line - line) >= 0.5
                        or abs(last.odds_over - odds_over) >= 0.05
                    ):
                        direction = "up" if line > last.line else "down"
                        event_record = LineMovementEvent(
                            prop_id=prop.id,
                            bookmaker=book_key,
                            line_before=last.line,
                            line_after=line,
                            odds_over_before=last.odds_over,
                            odds_over_after=odds_over,
                            odds_under_before=last.odds_under,
                            odds_under_after=odds_under,
                            direction=direction,
                        )
                        db.add(event_record)

                    self._last_snapshots[cache_key] = snapshot
                    written += 1

        await db.flush()
        return written

    async def _get_or_create_player(
        self, name: str, sport: str, db: AsyncSession
    ) -> Player:
        result = await db.execute(
            select(Player).where(Player.name == name, Player.sport == sport)
        )
        player = result.scalar_one_or_none()
        if not player:
            player = Player(
                external_id=f"{sport}_{name.lower().replace(' ', '_')}",
                name=name,
                sport=sport,
                team="TBD",
                team_abbr="TBD",
                position="TBD",
            )
            db.add(player)
            await db.flush()
        return player

    async def _get_or_create_prop(
        self,
        player: Player,
        sport: str,
        stat_type: str,
        line: float,
        game_date: date,
        opponent: str,
        db: AsyncSession,
    ) -> Prop:
        result = await db.execute(
            select(Prop).where(
                Prop.player_id == player.id,
                Prop.stat_type == stat_type,
                Prop.game_date == game_date,
            )
        )
        prop = result.scalar_one_or_none()
        if not prop:
            prop = Prop(
                player_id=player.id,
                sport=sport,
                stat_type=stat_type,
                line=line,
                game_date=game_date,
                opponent_team=opponent,
            )
            db.add(prop)
            await db.flush()
        elif prop.line != line:
            prop.line = line   # update consensus line
        return prop
