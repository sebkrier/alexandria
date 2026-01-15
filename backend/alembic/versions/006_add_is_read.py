"""Add is_read column to articles

Revision ID: 006
Revises: 005
Create Date: 2025-01-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if column already exists
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "is_read" not in columns:
        op.add_column(
            "articles", sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false")
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "is_read" in columns:
        op.drop_column("articles", "is_read")
