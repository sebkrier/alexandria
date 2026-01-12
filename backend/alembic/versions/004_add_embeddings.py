"""Add embedding column for semantic search

Revision ID: 004
Revises: 003
Create Date: 2025-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension - OpenAI text-embedding-3-small uses 1536
EMBEDDING_DIM = 1536


def upgrade() -> None:
    conn = op.get_bind()

    # Enable pgvector extension
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Check if column already exists
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('articles')]

    if 'embedding' not in columns:
        # Add embedding column using raw SQL (pgvector type)
        conn.execute(text(f"ALTER TABLE articles ADD COLUMN embedding vector({EMBEDDING_DIM})"))

        # Create HNSW index for fast similarity search
        # HNSW is faster than IVFFlat for most use cases
        conn.execute(text(
            "CREATE INDEX ix_articles_embedding ON articles "
            "USING hnsw (embedding vector_cosine_ops)"
        ))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('articles')]

    if 'embedding' in columns:
        conn.execute(text("DROP INDEX IF EXISTS ix_articles_embedding"))
        conn.execute(text("ALTER TABLE articles DROP COLUMN embedding"))
