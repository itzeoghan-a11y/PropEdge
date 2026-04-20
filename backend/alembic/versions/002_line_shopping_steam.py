"""line shopping + steam signal columns

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ev_opportunities: line shopping + steam fields ─────────────
    op.add_column(
        "ev_opportunities",
        sa.Column(
            "is_best_available_line",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "ev_opportunities",
        sa.Column(
            "steam_boosted",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "ev_opportunities",
        sa.Column("line_at_flag", sa.Float, nullable=True),
    )
    op.add_column(
        "ev_opportunities",
        sa.Column("closing_line_odds", sa.Float, nullable=True),
    )

    # Index to find best-available bets quickly
    op.create_index(
        "ix_ev_best_available",
        "ev_opportunities",
        ["prop_id", "direction", "is_best_available_line"],
    )

    # ── props: line shopping consensus + dispersion ────────────────
    op.add_column(
        "props",
        sa.Column("consensus_line", sa.Float, nullable=True),
    )
    op.add_column(
        "props",
        sa.Column("line_dispersion", sa.Float, nullable=True),
    )
    op.add_column(
        "props",
        sa.Column("best_over_book", sa.String(32), nullable=True),
    )
    op.add_column(
        "props",
        sa.Column("best_over_odds", sa.Float, nullable=True),
    )
    op.add_column(
        "props",
        sa.Column("best_under_book", sa.String(32), nullable=True),
    )
    op.add_column(
        "props",
        sa.Column("best_under_odds", sa.Float, nullable=True),
    )
    op.add_column(
        "props",
        sa.Column("soft_book_count", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    # props
    for col in [
        "consensus_line", "line_dispersion", "best_over_book",
        "best_over_odds", "best_under_book", "best_under_odds", "soft_book_count",
    ]:
        op.drop_column("props", col)

    # ev_opportunities
    op.drop_index("ix_ev_best_available", table_name="ev_opportunities")
    for col in ["is_best_available_line", "steam_boosted", "line_at_flag", "closing_line_odds"]:
        op.drop_column("ev_opportunities", col)
