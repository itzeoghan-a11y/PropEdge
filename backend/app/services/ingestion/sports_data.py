"""
Sports data ingestion — player game logs and team defensive rankings.

Connects to the SportsDataIO v3 API for NBA, NFL, MLB, and NHL.
Each sport uses date-based endpoints for game logs; defense rankings
are refreshed nightly. Falls back gracefully when the API key is absent.
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

# SportsDataIO v3 base URLs per sport
_SPORT_BASE = {
    "basketball_nba": "https://api.sportsdata.io/v3/nba/stats/json",
    "americanfootball_nfl": "https://api.sportsdata.io/v3/nfl/stats/json",
    "baseball_mlb": "https://api.sportsdata.io/v3/mlb/stats/json",
    "icehockey_nhl": "https://api.sportsdata.io/v3/nhl/stats/json",
}

# Field mapping: SportsDataIO field name -> PlayerGameLog attribute
_NBA_FIELDS = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "ThreePointersMade": "three_pointers_made",
    "Steals": "steals",
    "BlockedShots": "blocks",
    "Turnovers": "turnovers",
    "FieldGoalsAttempted": "field_goals_attempted",
    "FieldGoalsMade": "field_goals_made",
    "Minutes": "minutes_played",
    "UsageRatePercentage": "usage_rate",
}

_NFL_FIELDS = {
    "PassingYards": "passing_yards",
    "PassingTouchdowns": "passing_touchdowns",
    "PassingInterceptions": "interceptions",
    "RushingYards": "rushing_yards",
    "RushingTouchdowns": "rushing_touchdowns",
    "ReceivingYards": "receiving_yards",
    "Receptions": "receptions",
    "ReceivingTouchdowns": "receiving_touchdowns",
    "ReceivingTargets": "targets",
}

_MLB_FIELDS = {
    "Hits": "hits",
    "HomeRuns": "home_runs",
    "RunsBattedIn": "rbis",
    "PitchingStrikeouts": "strikeouts_pitcher",
    "EarnedRuns": "earned_runs",
}

_NHL_FIELDS = {
    "Goals": "goals",
    "Assists": "hockey_assists",
    "Shots": "shots_on_goal",
    "PlusMinus": "plus_minus",
}

_SPORT_FIELDS = {
    "basketball_nba": _NBA_FIELDS,
    "americanfootball_nfl": _NFL_FIELDS,
    "baseball_mlb": _MLB_FIELDS,
    "icehockey_nhl": _NHL_FIELDS,
}


class SportsDataCollector:
    """
    Fetches player game logs and team defense rankings from SportsDataIO.

    Requires SPORTS_DATA_API_KEY in config. When missing, methods are
    no-ops so the rest of the ingestion pipeline continues without error.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

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

    # ── Public entry points ──────────────────────────────────────────────────

    async def ingest_recent_logs(
        self, sport: str, db: AsyncSession, days_back: int = 3
    ) -> int:
        """
        Pull game logs for the past N days and upsert into player_game_logs.
        Returns the number of records written.
        """
        if not settings.sports_data_api_key:
            log.debug("SPORTS_DATA_API_KEY not set — skipping game log ingestion for %s", sport)
            return 0

        base = _SPORT_BASE.get(sport)
        if not base:
            return 0

        total = 0
        for delta in range(days_back):
            target_date = date.today() - timedelta(days=delta)
            try:
                raw_logs = await self._fetch_logs_for_date(sport, base, target_date)
                total += await self._upsert_logs(sport, raw_logs, db)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    log.debug("No game log data for %s on %s", sport, target_date)
                else:
                    log.warning("HTTP error fetching %s logs for %s: %s", sport, target_date, exc)
            except Exception as exc:
                log.warning("Failed to fetch %s logs for %s: %s", sport, target_date, exc)

        return total

    async def update_defense_rankings(
        self, sport: str, season: str, db: AsyncSession
    ) -> int:
        """Refresh team defensive rankings for a sport/season (called nightly)."""
        if not settings.sports_data_api_key:
            log.debug("SPORTS_DATA_API_KEY not set — skipping defense rankings for %s", sport)
            return 0

        base = _SPORT_BASE.get(sport)
        if not base:
            return 0

        try:
            if sport == "basketball_nba":
                return await self._update_nba_defense(base, season, db)
            elif sport == "americanfootball_nfl":
                return await self._update_nfl_defense(base, season, db)
            else:
                log.debug("Defense rankings not yet implemented for %s", sport)
                return 0
        except Exception as exc:
            log.warning("Defense rankings update failed for %s: %s", sport, exc)
            return 0

    # ── Fetch helpers ────────────────────────────────────────────────────────

    async def _fetch_logs_for_date(
        self, sport: str, base: str, target_date: date
    ) -> list[dict]:
        """Return raw log dicts for all players on a given game date."""
        date_str = target_date.strftime("%Y-%m-%d") if sport != "americanfootball_nfl" else target_date.strftime("%Y/%m/%d")

        if sport == "basketball_nba":
            return await self._get(f"{base}/PlayerGameStatsByDate/{date_str}")
        elif sport == "americanfootball_nfl":
            # NFL uses season/week rather than calendar date
            season, week = _nfl_date_to_season_week(target_date)
            if season is None:
                return []
            return await self._get(f"{base}/PlayerGameStatsByWeek/{season}/{week}")
        elif sport == "baseball_mlb":
            return await self._get(f"{base}/PlayerGameStatsByDate/{date_str}")
        elif sport == "icehockey_nhl":
            return await self._get(f"{base}/PlayerGameStatsByDate/{date_str}")
        return []

    # ── Upsert ───────────────────────────────────────────────────────────────

    async def _upsert_logs(
        self, sport: str, raw_logs: list[dict], db: AsyncSession
    ) -> int:
        field_map = _SPORT_FIELDS.get(sport, {})
        written = 0

        for raw in raw_logs:
            # SportsDataIO uses "Name" for the player's full name
            player_name = raw.get("Name", "")
            if not player_name:
                continue

            log_obj = self._parse_log(sport, field_map, raw)
            if log_obj is None:
                continue

            # Resolve player from DB by name+sport
            player = await self._resolve_player(player_name, sport, db)
            if player is None:
                continue
            log_obj.player_id = player.id

            existing = await db.execute(
                select(PlayerGameLog).where(
                    PlayerGameLog.player_id == player.id,
                    PlayerGameLog.game_date == log_obj.game_date,
                    PlayerGameLog.opponent_team == log_obj.opponent_team,
                )
            )
            if existing.scalar_one_or_none() is None:
                db.add(log_obj)
                written += 1

        await db.flush()
        return written

    def _parse_log(
        self, sport: str, field_map: dict[str, str], raw: dict
    ) -> PlayerGameLog | None:
        """Parse a raw SportsDataIO game log dict into a PlayerGameLog."""
        # SportsDataIO uses "GameDate" or "DateTime" depending on sport
        date_str = raw.get("GameDate") or raw.get("DateTime") or ""
        try:
            # Handle ISO format with or without time component
            if "T" in date_str:
                game_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            else:
                game_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            return None

        # Skip games where the player didn't play
        if raw.get("FantasyPointsFanDuel") is None and raw.get("Minutes") in (None, 0):
            return None

        opponent = raw.get("Opponent", raw.get("OpponentID", ""))
        home_or_away = raw.get("HomeOrAway", "HOME")

        gl = PlayerGameLog(
            player_id=0,  # filled by _upsert_logs after player resolution
            game_date=game_date,
            opponent_team=str(opponent),
            opponent_abbr=str(opponent)[:3].upper(),
            is_home=home_or_away == "HOME",
            minutes_played=raw.get("Minutes"),
        )

        # Map sport-specific stats
        for api_field, model_attr in field_map.items():
            val = raw.get(api_field)
            if val is not None:
                setattr(gl, model_attr, val)

        return gl

    async def _resolve_player(
        self, name: str, sport: str, db: AsyncSession
    ) -> Player | None:
        """Look up a player by name+sport in our DB; return None if not found."""
        result = await db.execute(
            select(Player).where(Player.name == name, Player.sport == sport)
        )
        return result.scalar_one_or_none()

    # ── Defense rankings helpers ──────────────────────────────────────────────

    async def _update_nba_defense(
        self, base: str, season: str, db: AsyncSession
    ) -> int:
        data = await self._get(f"{base}/TeamSeasonStats/{season}")
        written = 0
        for team in data:
            abbr = team.get("Team", "")
            if not abbr:
                continue
            existing = await db.execute(
                select(TeamDefenseRanking).where(
                    TeamDefenseRanking.sport == "basketball_nba",
                    TeamDefenseRanking.team_abbr == abbr,
                    TeamDefenseRanking.season == season,
                )
            )
            ranking = existing.scalar_one_or_none()
            if ranking is None:
                ranking = TeamDefenseRanking(
                    sport="basketball_nba",
                    team_abbr=abbr,
                    season=season,
                )
                db.add(ranking)
                written += 1
            ranking.points_allowed_per_game = team.get("OpponentPoints")
            ranking.opponent_field_goal_pct = team.get("OpponentFieldGoalsPercentage")

        await db.flush()
        return written

    async def _update_nfl_defense(
        self, base: str, season: str, db: AsyncSession
    ) -> int:
        data = await self._get(f"{base}/TeamSeasonStats/{season}")
        written = 0
        for team in data:
            abbr = team.get("Team", "")
            if not abbr:
                continue
            existing = await db.execute(
                select(TeamDefenseRanking).where(
                    TeamDefenseRanking.sport == "americanfootball_nfl",
                    TeamDefenseRanking.team_abbr == abbr,
                    TeamDefenseRanking.season == season,
                )
            )
            ranking = existing.scalar_one_or_none()
            if ranking is None:
                ranking = TeamDefenseRanking(
                    sport="americanfootball_nfl",
                    team_abbr=abbr,
                    season=season,
                )
                db.add(ranking)
                written += 1
            ranking.points_allowed_per_game = team.get("PointsAllowedByDefenseSpecialTeams")
            ranking.pass_yards_allowed = team.get("PassingYardsAllowed")
            ranking.rush_yards_allowed = team.get("RushingYardsAllowed")

        await db.flush()
        return written


# ── Utility ──────────────────────────────────────────────────────────────────

def _nfl_date_to_season_week(d: date) -> tuple[str | None, int | None]:
    """
    Approximate conversion of a calendar date to NFL season + week.
    NFL regular season runs Week 1 (first Thursday of September) through
    Week 18, then playoffs. Returns (None, None) outside of season.
    """
    year = d.year
    # NFL season starts early September
    season_start = date(year, 9, 1)
    # Find first Thursday of September
    while season_start.weekday() != 3:  # 3 = Thursday
        season_start += timedelta(days=1)

    if d < season_start:
        # Could be previous year's playoffs (Jan/Feb)
        if d.month <= 2:
            year -= 1
            season_start = date(year, 9, 1)
            while season_start.weekday() != 3:
                season_start += timedelta(days=1)
        else:
            return None, None

    delta_days = (d - season_start).days
    week = delta_days // 7 + 1
    if week < 1 or week > 22:  # 18 regular + 4 playoff
        return None, None

    return str(year), week
