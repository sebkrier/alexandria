"""Change embedding dimension from 1536 to 768 for EmbeddingGemma

Revision ID: 005
Revises: 004
Create Date: 2025-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New dimension for EmbeddingGemma (768) vs OpenAI (1536)
NEW_EMBEDDING_DIM = 768
OLD_EMBEDDING_DIM = 1536


def upgrade() -> None:
    conn = op.get_bind()

    # Drop the existing HNSW index
    conn.execute(text("DROP INDEX IF EXISTS ix_articles_embedding"))

    # Drop and recreate column with new dimension
    # (ALTER COLUMN TYPE doesn't work well with pgvector)
    conn.execute(text("ALTER TABLE articles DROP COLUMN IF EXISTS embedding"))
    conn.execute(text(f"ALTER TABLE articles ADD COLUMN embedding vector({NEW_EMBEDDING_DIM})"))

    # Recreate HNSW index
    conn.execute(text(
        "CREATE INDEX ix_articles_embedding ON articles "
        "USING hnsw (embedding vector_cosine_ops)"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    # Drop the HNSW index
    conn.execute(text("DROP INDEX IF EXISTS ix_articles_embedding"))

    # Revert to old dimension
    conn.execute(text("ALTER TABLE articles DROP COLUMN IF EXISTS embedding"))
    conn.execute(text(f"ALTER TABLE articles ADD COLUMN embedding vector({OLD_EMBEDDING_DIM})"))

    # Recreate index
    conn.execute(text(
        "CREATE INDEX ix_articles_embedding ON articles "
        "USING hnsw (embedding vector_cosine_ops)"
    ))
