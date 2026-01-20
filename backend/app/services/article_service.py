from uuid import UUID
from typing import Sequence
from fastapi import BackgroundTasks
from sqlalchemy import select, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, defer

from app.models.article import Article, ProcessingStatus, SourceType
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.extractors import extract_content
from app.database import async_session_maker
from app.ai.service import AIService
import logging

logger = logging.getLogger(__name__)

async def process_article_background_task(article_id: UUID, user_id: UUID):
    """Background task to process article with AI"""
    logger.info(f"Background task started for article {article_id}")
    async with async_session_maker() as db:
        try:
            ai_service = AIService(db)
            await ai_service.process_article(article_id=article_id, user_id=user_id)
            logger.info(f"Background processing completed for article {article_id}")
        except Exception as e:
            logger.error(f"Background processing failed for article {article_id}: {e}", exc_info=True)
            # Update status to failed
            try:
                result = await db.execute(select(Article).where(Article.id == article_id))
                article = result.scalar_one_or_none()
                if article:
                    article.processing_status = ProcessingStatus.FAILED
                    article.processing_error = str(e)
                    await db.commit()
            except Exception as update_err:
                logger.error(f"Failed to update article status: {update_err}")

class ArticleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_article_from_url(
        self,
        url: str,
        user_id: UUID,
        background_tasks: BackgroundTasks | None = None
    ) -> Article:
        """Create a new article from a URL"""
        # Extract content
        content = await extract_content(url=url)
        source_type = SourceType(content.source_type)

        article = Article(
            user_id=user_id,
            source_type=source_type,
            original_url=content.original_url or url,
            title=content.title,
            authors=content.authors,
            publication_date=content.publication_date,
            extracted_text=content.text,
            word_count=len(content.text.split()) if content.text else None,
            article_metadata=content.metadata,
            processing_status=ProcessingStatus.PENDING,
        )

        self.db.add(article)
        await self.db.commit()
        await self.db.refresh(article)

        if background_tasks:
            background_tasks.add_task(process_article_background_task, article.id, user_id)

        # Reload with relationships for response
        return await self.get_article(article.id, user_id)

    async def create_article_from_upload(
        self,
        file_path: str,
        filename: str,
        user_id: UUID,
        background_tasks: BackgroundTasks | None = None
    ) -> Article:
        """Create a new article from a PDF upload"""
        # Extract content from PDF
        extracted = await extract_content(file_path=file_path)

        # Create article
        article = Article(
            user_id=user_id,
            source_type=SourceType.PDF,
            title=extracted.title or filename,
            authors=extracted.authors,
            extracted_text=extracted.text,
            word_count=len(extracted.text.split()) if extracted.text else None,
            file_path=f"uploads/{user_id}/{filename}", # Placeholder path logic as per original
            article_metadata=extracted.metadata,
            processing_status=ProcessingStatus.PENDING,
        )

        self.db.add(article)
        await self.db.commit()
        await self.db.refresh(article)

        if background_tasks:
            background_tasks.add_task(process_article_background_task, article.id, user_id)

        return await self.get_article(article.id, user_id)

    async def get_article(self, article_id: UUID, user_id: UUID) -> Article | None:
        """Get a single article with relationships loaded"""
        query = (
            select(Article)
            .where(Article.id == article_id, Article.user_id == user_id)
            .options(
                selectinload(Article.categories).selectinload(ArticleCategory.category),
                selectinload(Article.tags).selectinload(ArticleTag.tag),
                selectinload(Article.color),
                selectinload(Article.notes),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_articles(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        category_id: UUID | None = None,
        tag_id: UUID | None = None,
        color_id: UUID | None = None,
        status: ProcessingStatus | None = None,
        is_read: bool | None = None,
    ) -> tuple[Sequence[Article], int]:
        """List articles with filtering and pagination. Optimized to defer heavy text."""

        # Base query - Optimization: Defer extracted_text
        query = (
            select(Article)
            .where(Article.user_id == user_id)
            .options(
                selectinload(Article.categories).selectinload(ArticleCategory.category),
                selectinload(Article.tags).selectinload(ArticleTag.tag),
                selectinload(Article.color),
                defer(Article.extracted_text), # Optimization: Don't load full text for list
                selectinload(Article.notes),
            )
        )

        ts_query = None

        if search:
             # Full-text search
             from sqlalchemy import func as sqla_func
             # Note: logic adapted from htmx.py and articles.py which differed slightly
             # articles.py used match(search), htmx.py used plainto_tsquery + ILIKE
             # We'll use the robust approach from htmx.py/articles.py

             ts_query = sqla_func.plainto_tsquery("english", search)

             # Subquery for tags (from htmx.py)
             from app.models.tag import Tag
             tag_match_subquery = (
                select(ArticleTag.article_id)
                .join(Tag, ArticleTag.tag_id == Tag.id)
                .where(Tag.name.ilike(f"%{search}%"))
             )

             query = query.where(
                or_(
                    Article.title.ilike(f"%{search}%"),
                    Article.search_vector.op("@@")(ts_query),
                    Article.id.in_(tag_match_subquery),
                )
            )

        if category_id:
            # Recursive category retrieval
            from app.models.category import Category

            async def get_descendant_ids(cat_id: UUID) -> list[UUID]:
                result = await self.db.execute(select(Category.id).where(Category.parent_id == cat_id))
                child_ids = [row[0] for row in result.all()]
                descendants = list(child_ids)
                for child_id in child_ids:
                    descendants.extend(await get_descendant_ids(child_id))
                return descendants

            category_ids = [category_id] + await get_descendant_ids(category_id)
            query = query.join(ArticleCategory).where(ArticleCategory.category_id.in_(category_ids))

        if tag_id:
             query = query.join(ArticleTag).where(ArticleTag.tag_id == tag_id)

        if color_id:
             query = query.where(Article.color_id == color_id)

        if status:
             query = query.where(Article.processing_status == status)

        if is_read is not None:
             query = query.where(Article.is_read == is_read)

        # Distinct for joins if filtering by related tables
        if category_id or tag_id:
            query = query.distinct()

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Order by relevance if searching, else date
        if search and ts_query is not None:
            rank = func.ts_rank(Article.search_vector, ts_query)
            query = query.order_by(rank.desc(), Article.created_at.desc())
        else:
            query = query.order_by(Article.created_at.desc())

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        articles = result.scalars().all()

        return articles, total

    async def update_article(
        self,
        article_id: UUID,
        user_id: UUID,
        title: str | None = None,
        color_id: UUID | None = None,
        is_read: bool | None = None,
        category_ids: list[UUID] | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> Article | None:
        """Update an article"""
        result = await self.db.execute(
            select(Article).where(Article.id == article_id, Article.user_id == user_id)
        )
        article = result.scalar_one_or_none()

        if not article:
            return None

        if title is not None:
            article.title = title
        if color_id is not None:
            article.color_id = color_id
        if is_read is not None:
            article.is_read = is_read

        if category_ids is not None:
            # Remove existing categories using DELETE statement
            await self.db.execute(delete(ArticleCategory).where(ArticleCategory.article_id == article_id))

            # Add new categories
            for i, cat_id in enumerate(category_ids):
                ac = ArticleCategory(
                    article_id=article_id,
                    category_id=cat_id,
                    is_primary=(i == 0),
                )
                self.db.add(ac)

        if tag_ids is not None:
             # Remove existing tags using DELETE statement
            await self.db.execute(delete(ArticleTag).where(ArticleTag.article_id == article_id))
            # Add new tags
            for tag_id in tag_ids:
                at = ArticleTag(
                    article_id=article_id,
                    tag_id=tag_id,
                )
                self.db.add(at)

        await self.db.commit()

        # Reload with relationships
        return await self.get_article(article_id, user_id)

    async def delete_article(self, article_id: UUID, user_id: UUID) -> bool:
        """Delete an article"""
        result = await self.db.execute(
            select(Article).where(Article.id == article_id, Article.user_id == user_id)
        )
        article = result.scalar_one_or_none()
        if not article:
            return False

        await self.db.delete(article)
        await self.db.commit()
        return True
