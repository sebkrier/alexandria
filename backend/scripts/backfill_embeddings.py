#!/usr/bin/env python3
"""
Backfill embeddings for existing articles using local all-mpnet-base-v2 model.

Usage:
    python scripts/backfill_embeddings.py

This script:
1. Finds all articles without embeddings
2. Generates embeddings using the local all-mpnet-base-v2 model
3. Updates the database in batches with progress logging

Requirements:
- pgvector extension must be enabled
- Articles table must have embedding column (768 dims)
- sentence-transformers must be installed

"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check pgvector availability
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EMBEDDING_DIM, generate_embedding, is_model_available
from app.database import async_session_maker
from app.models.article import Article, ProcessingStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 10  # Process N articles before committing


def generate_article_embedding(article: Article) -> list[float] | None:
    """Generate embedding for a single article."""
    parts = []

    if article.title:
        parts.append(f"Title: {article.title}")

    if article.summary:
        parts.append(f"Summary: {article.summary}")

    if article.extracted_text:
        content_excerpt = article.extracted_text[:4000]
        parts.append(f"Content: {content_excerpt}")

    if not parts:
        return None

    text_to_embed = "\n\n".join(parts)
    return generate_embedding(text_to_embed)


async def backfill_all_embeddings(db: AsyncSession) -> tuple[int, int]:
    """Backfill embeddings for all articles missing them."""
    # Count articles needing embeddings
    count_query = (
        select(func.count(Article.id))
        .where(Article.processing_status == ProcessingStatus.COMPLETED)
        .where(Article.embedding.is_(None))
    )
    total = (await db.execute(count_query)).scalar()

    if total == 0:
        logger.info("No articles need embeddings")
        return 0, 0

    logger.info(f"Found {total} articles needing embeddings")

    # Process in batches
    processed = 0
    failed = 0

    while True:
        # Fetch batch (always get articles with null embeddings)
        batch_query = (
            select(Article)
            .where(Article.processing_status == ProcessingStatus.COMPLETED)
            .where(Article.embedding.is_(None))
            .limit(BATCH_SIZE)
        )
        result = await db.execute(batch_query)
        articles = result.scalars().all()

        if not articles:
            break

        # Process batch
        for article in articles:
            embedding = generate_article_embedding(article)

            if embedding:
                article.embedding = embedding
                processed += 1
                logger.info(f"  [{processed}/{total}] Embedded: {article.title[:50]}")
            else:
                failed += 1
                logger.warning(f"  Failed: {article.title[:50]}")

        # Commit batch
        await db.commit()

    return processed, failed


async def main():
    """Main backfill routine."""
    logger.info("=" * 60)
    logger.info("Starting embedding backfill with all-mpnet-base-v2")
    logger.info("=" * 60)

    if not PGVECTOR_AVAILABLE:
        logger.error("pgvector is not installed. Please install it first:")
        logger.error("  pip install pgvector")
        logger.error("And ensure the PostgreSQL extension is enabled:")
        logger.error("  CREATE EXTENSION IF NOT EXISTS vector;")
        return

    # Check if Article model has embedding attribute
    if not hasattr(Article, "embedding"):
        logger.error("Article model doesn't have embedding column.")
        logger.error("Run the migration first: alembic upgrade head")
        return

    # Check if model can be loaded
    logger.info(f"Loading all-mpnet-base-v2 model (embedding dim={EMBEDDING_DIM})...")
    if not is_model_available():
        logger.error("Failed to load all-mpnet-base-v2 model.")
        logger.error("Make sure sentence-transformers is installed:")
        logger.error("  pip install sentence-transformers")
        return
    logger.info("Model loaded successfully!")

    async with async_session_maker() as db:
        processed, failed = await backfill_all_embeddings(db)

        logger.info("=" * 60)
        logger.info("Backfill complete!")
        logger.info(f"  Processed: {processed}")
        logger.info(f"  Failed: {failed}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
