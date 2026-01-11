"""Add word_count column to articles

Revision ID: 003
Revises: 002
Create Date: 2025-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column already exists
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('articles')]

    if 'word_count' not in columns:
        op.add_column('articles', sa.Column('word_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('articles')]

    if 'word_count' in columns:
        op.drop_column('articles', 'word_count')
