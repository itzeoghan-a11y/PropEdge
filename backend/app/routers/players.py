from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database import get_db
from app.models import Player, PlayerGameLog, Prop
from app.models.user import User

router = APIRouter(prefix="/players", tags=["players"])


@router.get("")
async def list_players(
    sport: str | None = None,
    team: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Player)
    if sport:
        query = query.where(Player.sport == sport)
    if team:
        query = query.where(Player.team.ilike(f"%{team}%"))
    if search:
        query = query.where(Player.name.ilike(f"%{search}%"))
    query = query.limit(limit)

    result = await db.execute(query)
    players = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "sport": p.sport,
            "team": p.team,
            "position": p.position,
            "injury_status": p.injury_status,
        }
        for p in players
    ]


@router.get("/{player_id}")
async def player_detail(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Game logs (last 20)
    logs_result = await db.execute(
        select(PlayerGameLog)
        .where(PlayerGameLog.player_id == player_id)
        .order_by(desc(PlayerGameLog.game_date))
        .limit(20)
    )
    logs = logs_result.scalars().all()

    # Recent props
    props_result = await db.execute(
        select(Prop)
        .where(Prop.player_id == player_id, Prop.is_active.is_(True))
        .order_by(desc(Prop.game_date))
        .limit(10)
    )
    props = props_result.scalars().all()

    return {
        "id": player.id,
        "name": player.name,
        "sport": player.sport,
        "team": player.team,
        "team_abbr": player.team_abbr,
        "position": player.position,
        "injury_status": player.injury_status,
        "game_logs": [
            {
                "game_date": g.game_date,
                "opponent_team": g.opponent_team,
                "is_home": g.is_home,
                "minutes_played": g.minutes_played,
                "points": g.points,
                "rebounds": g.rebounds,
                "assists": g.assists,
                "three_pointers_made": g.three_pointers_made,
                "steals": g.steals,
                "blocks": g.blocks,
                "passing_yards": g.passing_yards,
                "rushing_yards": g.rushing_yards,
                "receiving_yards": g.receiving_yards,
                "receptions": g.receptions,
                "usage_rate": g.usage_rate,
            }
            for g in logs
        ],
        "active_props": [
            {
                "id": p.id,
                "stat_type": p.stat_type,
                "line": p.line,
                "game_date": p.game_date,
                "opponent_team": p.opponent_team,
            }
            for p in props
        ],
    }
