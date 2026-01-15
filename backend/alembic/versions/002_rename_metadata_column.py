"""Rename metadata column to article_metadata

Revision ID: 002
Revises: 001
Create Date: 2025-01-10

"""

from collections.abc import Sequence

from sqlalchemy import inspect

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if rename is needed (column might already be named article_metadata)
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "metadata" in columns and "article_metadata" not in columns:
        # Rename metadata column to article_metadata to avoid conflict with SQLAlchemy
        op.alter_column("articles", "metadata", new_column_name="article_metadata")
    # If article_metadata already exists, migration is already applied


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "article_metadata" in columns and "metadata" not in columns:
        op.alter_column("articles", "article_metadata", new_column_name="metadata")
