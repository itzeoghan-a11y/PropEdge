"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("full_name", sa.String(128), nullable=True),
        sa.Column("tier", sa.String(16), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("subscription_status", sa.String(32), nullable=False, server_default="inactive"),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("discord_webhook", sa.String(256), nullable=True),
        sa.Column("phone_number", sa.String(32), nullable=True),
        sa.Column("alert_min_ev", sa.Float, nullable=False, server_default="0.05"),
        sa.Column("alert_min_confidence", sa.Float, nullable=False, server_default="60.0"),
        sa.Column("alert_steam", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime, nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── players ────────────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("sport", sa.String(32), nullable=False),
        sa.Column("team", sa.String(64), nullable=False),
        sa.Column("team_abbr", sa.String(8), nullable=False),
        sa.Column("position", sa.String(16), nullable=False),
        sa.Column("jersey_number", sa.String(4), nullable=True),
        sa.Column("injury_status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_players_external_id", "players", ["external_id"], unique=True)
    op.create_index("ix_players_name", "players", ["name"])
    op.create_index("ix_players_sport", "players", ["sport"])

    # ── player_game_logs ───────────────────────────────────────────
    op.create_table(
        "player_game_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_date", sa.Date, nullable=False),
        sa.Column("opponent_team", sa.String(64), nullable=False),
        sa.Column("opponent_abbr", sa.String(8), nullable=False),
        sa.Column("is_home", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("result", sa.String(4), nullable=True),
        sa.Column("minutes_played", sa.Float, nullable=True),
        # Basketball
        sa.Column("points", sa.Float, nullable=True),
        sa.Column("rebounds", sa.Float, nullable=True),
        sa.Column("assists", sa.Float, nullable=True),
        sa.Column("three_pointers_made", sa.Float, nullable=True),
        sa.Column("steals", sa.Float, nullable=True),
        sa.Column("blocks", sa.Float, nullable=True),
        sa.Column("turnovers", sa.Float, nullable=True),
        sa.Column("field_goals_attempted", sa.Float, nullable=True),
        sa.Column("field_goals_made", sa.Float, nullable=True),
        sa.Column("usage_rate", sa.Float, nullable=True),
        sa.Column("true_shooting_pct", sa.Float, nullable=True),
        # Football
        sa.Column("passing_yards", sa.Float, nullable=True),
        sa.Column("passing_touchdowns", sa.Float, nullable=True),
        sa.Column("interceptions", sa.Float, nullable=True),
        sa.Column("rushing_yards", sa.Float, nullable=True),
        sa.Column("rushing_touchdowns", sa.Float, nullable=True),
        sa.Column("receiving_yards", sa.Float, nullable=True),
        sa.Column("receptions", sa.Float, nullable=True),
        sa.Column("receiving_touchdowns", sa.Float, nullable=True),
        sa.Column("targets", sa.Float, nullable=True),
        # Baseball
        sa.Column("hits", sa.Float, nullable=True),
        sa.Column("home_runs", sa.Float, nullable=True),
        sa.Column("rbis", sa.Float, nullable=True),
        sa.Column("strikeouts_pitcher", sa.Float, nullable=True),
        sa.Column("earned_runs", sa.Float, nullable=True),
        # Hockey
        sa.Column("goals", sa.Float, nullable=True),
        sa.Column("hockey_assists", sa.Float, nullable=True),
        sa.Column("shots_on_goal", sa.Float, nullable=True),
        sa.Column("plus_minus", sa.Float, nullable=True),
        # Context
        sa.Column("team_pace", sa.Float, nullable=True),
        sa.Column("opponent_def_rating", sa.Float, nullable=True),
        sa.Column("opponent_pace", sa.Float, nullable=True),
        sa.Column("days_rest", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_pgl_player_id", "player_game_logs", ["player_id"])
    op.create_index("ix_pgl_game_date", "player_game_logs", ["game_date"])

    # ── props ──────────────────────────────────────────────────────
    op.create_table(
        "props",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.String(64), nullable=True),
        sa.Column("sport", sa.String(32), nullable=False),
        sa.Column("stat_type", sa.String(64), nullable=False),
        sa.Column("line", sa.Float, nullable=False),
        sa.Column("game_date", sa.Date, nullable=False),
        sa.Column("opponent_team", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("actual_result", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_props_player_stat_game", "props", ["player_id", "stat_type", "game_date"])
    op.create_index("ix_props_sport", "props", ["sport"])

    # ── odds_snapshots ─────────────────────────────────────────────
    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("prop_id", sa.Integer, sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bookmaker", sa.String(32), nullable=False),
        sa.Column("line", sa.Float, nullable=False),
        sa.Column("odds_over", sa.Float, nullable=False),
        sa.Column("odds_under", sa.Float, nullable=False),
        sa.Column("is_sharp", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_odds_prop_book_time", "odds_snapshots", ["prop_id", "bookmaker", "recorded_at"])

    # ── line_movement_events ───────────────────────────────────────
    op.create_table(
        "line_movement_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("prop_id", sa.Integer, sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bookmaker", sa.String(32), nullable=False),
        sa.Column("line_before", sa.Float, nullable=False),
        sa.Column("line_after", sa.Float, nullable=False),
        sa.Column("odds_over_before", sa.Float, nullable=False),
        sa.Column("odds_over_after", sa.Float, nullable=False),
        sa.Column("odds_under_before", sa.Float, nullable=False),
        sa.Column("odds_under_after", sa.Float, nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("moved_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_lme_prop_book_moved", "line_movement_events", ["prop_id", "bookmaker", "moved_at"])

    # ── model_predictions ──────────────────────────────────────────
    op.create_table(
        "model_predictions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("prop_id", sa.Integer, sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("predicted_prob_over", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("features", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── ev_opportunities ───────────────────────────────────────────
    op.create_table(
        "ev_opportunities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("prop_id", sa.Integer, sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("bookmaker", sa.String(32), nullable=False),
        sa.Column("book_odds", sa.Float, nullable=False),
        sa.Column("implied_prob", sa.Float, nullable=False),
        sa.Column("model_prob", sa.Float, nullable=False),
        sa.Column("edge", sa.Float, nullable=False),
        sa.Column("ev", sa.Float, nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("sharp_prob", sa.Float, nullable=True),
        sa.Column("sharp_deviation", sa.Float, nullable=True),
        sa.Column("is_alerted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("won", sa.Boolean, nullable=True),
        sa.Column("found_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_ev_opportunities_found_at", "ev_opportunities", ["found_at"])

    # ── steam_alerts ───────────────────────────────────────────────
    op.create_table(
        "steam_alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("prop_id", sa.Integer, sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("books_moved", postgresql.JSON, nullable=False),
        sa.Column("line_before", sa.Float, nullable=False),
        sa.Column("line_after", sa.Float, nullable=False),
        sa.Column("line_delta", sa.Float, nullable=False),
        sa.Column("velocity", sa.Float, nullable=False),
        sa.Column("window_seconds", sa.Integer, nullable=False),
        sa.Column("is_reverse_line_movement", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_steam_alerts_detected_at", "steam_alerts", ["detected_at"])

    # ── team_defense_rankings ──────────────────────────────────────
    op.create_table(
        "team_defense_rankings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sport", sa.String(32), nullable=False),
        sa.Column("season", sa.String(12), nullable=False),
        sa.Column("team_abbr", sa.String(8), nullable=False),
        sa.Column("stat_type", sa.String(64), nullable=False),
        sa.Column("avg_allowed", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── backtest_results ───────────────────────────────────────────
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_label", sa.String(128), nullable=False),
        sa.Column("sport", sa.String(32), nullable=True),
        sa.Column("stat_type", sa.String(64), nullable=True),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        sa.Column("total_bets", sa.Integer, nullable=False),
        sa.Column("win_rate", sa.Float, nullable=False),
        sa.Column("roi", sa.Float, nullable=False),
        sa.Column("avg_ev", sa.Float, nullable=False),
        sa.Column("avg_confidence", sa.Float, nullable=False),
        sa.Column("calibration_error", sa.Float, nullable=False),
        sa.Column("parameters", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "backtest_results", "team_defense_rankings", "steam_alerts",
        "ev_opportunities", "model_predictions", "line_movement_events",
        "odds_snapshots", "props", "player_game_logs", "players", "users",
    ]:
        op.drop_table(table)
