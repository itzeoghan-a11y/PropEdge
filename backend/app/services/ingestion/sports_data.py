"""
Sports data ingestion — player game logs and team defensive rankings.

Designed to work with The Odds API player data + a supplemental stats source.
The collector is sport-aware: NBA, NFL, MLB, NHL all return different fields.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models import Player, PlayerGameLog, TeamDefenseRanking

log = logging.getLogger(__name__)
settings = get_settings()


class SportsDataCollector:
    """
    Fetches player game logs from an external stats API.

    In production, connect this to a provider like SportsRadar, MySportsFeeds,
    or RapidAPI's sports statistics endpoints.  The interface is intentionally
    generic so you can swap providers without touching the rest of the system.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._base = "https://api.sportsdata.io/v3"  # placeholder

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._client.get(
            url,
            params={"key": settings.sports_data_api_key, **(params or {})},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    async def ingest_recent_logs(
        self, sport: str, db: AsyncSession, days_back: int = 3
    ) -> int:
        """
        Fetch game logs for the past N days and upsert into player_game_logs.
        Returns the number of records written.
        """
        since = date.today() - timedelta(days=days_back)
        logs_written = 0

        players_result = await db.execute(
            select(Player).where(Player.sport == sport, Player.is_active.is_(True))
            if hasattr(Player, "is_active")
            else select(Player).where(Player.sport == sport)
        )
        players = players_result.scalars().all()

        for player in players:
            try:
                raw_logs = await self._fetch_game_logs(sport, player.external_id, since)
                for raw in raw_logs:
                    log_obj = self._parse_game_log(sport, player.id, raw)
                    if log_obj is None:
                        continue
                    # Upsert by (player_id, game_date, opponent)
                    existing = await db.execute(
                        select(PlayerGameLog).where(
                            PlayerGameLog.player_id == player.id,
                            PlayerGameLog.game_date == log_obj.game_date,
                            PlayerGameLog.opponent_team == log_obj.opponent_team,
                        )
                    )
                    if existing.scalar_one_or_none() is None:
                        db.add(log_obj)
                        logs_written += 1
            except Exception as exc:
                log.warning("Failed to fetch logs for player %s: %s", player.name, exc)

        await db.flush()
        return logs_written

    async def _fetch_game_logs(
        self, sport: str, external_id: str, since: date
    ) -> list[dict]:
        """
        Implement sport-specific API call here.
        Returns a list of raw game log dicts.
        """
        # Placeholder — real implementation queries the stats provider
        log.debug("Fetching game logs for %s since %s", external_id, since)
        return []

    def _parse_game_log(
        self, sport: str, player_id: int, raw: dict
    ) -> PlayerGameLog | None:
        try:
            game_date = datetime.strptime(raw.get("GameDate", ""), "%Y-%m-%d").date()
        except ValueError:
            return None

        gl = PlayerGameLog(
            player_id=player_id,
            game_date=game_date,
            opponent_team=raw.get("Opponent", ""),
            opponent_abbr=raw.get("OpponentAbbr", ""),
            is_home=raw.get("HomeOrAway", "HOME") == "HOME",
            minutes_played=raw.get("Minutes"),
        )

        if sport == "basketball_nba":
            gl.points = raw.get("Points")
            gl.rebounds = raw.get("Rebounds")
            gl.assists = raw.get("Assists")
            gl.three_pointers_made = raw.get("ThreePointersMade")
            gl.steals = raw.get("Steals")
            gl.blocks = raw.get("BlockedShots")
            gl.turnovers = raw.get("Turnovers")
            gl.field_goals_attempted = raw.get("FieldGoalsAttempted")
            gl.field_goals_made = raw.get("FieldGoalsMade")
            gl.usage_rate = raw.get("UsageRatePercentage")
            gl.team_pace = raw.get("Pace")
            gl.opponent_def_rating = raw.get("OpponentDefensiveRating")

        elif sport == "americanfootball_nfl":
            gl.passing_yards = raw.get("PassingYards")
            gl.passing_touchdowns = raw.get("PassingTouchdowns")
            gl.interceptions = raw.get("PassingInterceptions")
            gl.rushing_yards = raw.get("RushingYards")
            gl.rushing_touchdowns = raw.get("RushingTouchdowns")
            gl.receiving_yards = raw.get("ReceivingYards")
            gl.receptions = raw.get("Receptions")
            gl.receiving_touchdowns = raw.get("ReceivingTouchdowns")
            gl.targets = raw.get("ReceivingTargets")

        elif sport == "baseball_mlb":
            gl.hits = raw.get("Hits")
            gl.home_runs = raw.get("HomeRuns")
            gl.rbis = raw.get("RunsBattedIn")
            gl.strikeouts_pitcher = raw.get("PitchingStrikeouts")
            gl.earned_runs = raw.get("EarnedRuns")

        elif sport == "icehockey_nhl":
            gl.goals = raw.get("Goals")
            gl.hockey_assists = raw.get("Assists")
            gl.shots_on_goal = raw.get("Shots")
            gl.plus_minus = raw.get("PlusMinus")

        return gl

    async def update_defense_rankings(
        self, sport: str, season: str, db: AsyncSession
    ) -> int:
        """
        Refresh team defensive rankings for a sport/season.
        Called nightly via Celery beat.
        """
        # Placeholder — in production, query a stats provider endpoint
        log.info("Defense rankings update skipped (no stats provider configured)")
        return 0
