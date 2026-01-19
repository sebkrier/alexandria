"""
Background task functions for article processing.

These are module-level async functions that work with FastAPI's BackgroundTasks.
They're defined separately to avoid circular imports and ensure proper
handling with SQLAlchemy async sessions.
"""

import logging
from uuid import UUID

from sqlalchemy import select

from app.database import async_session_maker
from app.models.article import Article, ProcessingStatus

logger = logging.getLogger(__name__)


async def process_article_background(article_id: UUID, user_id: UUID) -> None:
    """
    Process an article in the background with AI.

    Generates summary, suggests tags, and categorizes the article.
    Updates article status to FAILED with error message on failure.

    This is a module-level function to work properly with FastAPI BackgroundTasks.

    Args:
        article_id: UUID of the article to process
        user_id: UUID of the user who owns the article
    """
    logger.info(f"Background task started for article {article_id}")

    async with async_session_maker() as db:
        try:
            # Import here to avoid circular imports
            from app.ai.service import AIService

            ai_service = AIService(db)
            await ai_service.process_article(article_id=article_id, user_id=user_id)
            logger.info(f"Background processing completed for article {article_id}")

        except Exception as e:
            logger.error(
                f"Background processing failed for article {article_id}: {e}",
                exc_info=True,
            )

            # Update article status to failed
            try:
                result = await db.execute(select(Article).where(Article.id == article_id))
                article = result.scalar_one_or_none()
                if article:
                    article.processing_status = ProcessingStatus.FAILED
                    article.processing_error = str(e)
                    await db.commit()
            except Exception as update_err:
                logger.error(f"Failed to update article status: {update_err}")
