"""
AI Service for processing articles.
Coordinates summarization, tagging, and categorization.
"""

import logging
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider, Summary, TagSuggestion, CategorySuggestion
from app.ai.factory import get_default_provider, get_ai_provider
from app.ai.embeddings import generate_embedding
from app.models.article import Article, ProcessingStatus
from app.models.category import Category
from app.models.tag import Tag
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered article processing"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_article(
        self,
        article_id: UUID,
        user_id: UUID,
        provider_id: UUID | None = None,
    ) -> Article:
        """
        Process an article: generate summary, suggest tags, and categorize.

        Args:
            article_id: The article to process
            user_id: Owner of the article
            provider_id: Optional specific provider to use

        Returns:
            Updated article
        """
        # Get the article
        result = await self.db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if not article:
            raise ValueError(f"Article {article_id} not found")

        # Update status
        article.processing_status = ProcessingStatus.PROCESSING
        await self.db.commit()

        try:
            # Get AI provider
            if provider_id:
                provider = await get_ai_provider(self.db, provider_id)
            else:
                provider = await get_default_provider(self.db, user_id)

            if not provider:
                raise ValueError("No AI provider configured. Please add one in Settings.")

            # 1. Generate summary
            logger.info(f"Generating summary for article {article_id}")
            source_type = article.source_type.value if hasattr(article.source_type, 'value') else str(article.source_type)
            summary = await provider.summarize(
                text=article.extracted_text,
                title=article.title,
                source_type=source_type,
            )

            # Store summary as markdown
            article.summary = summary.to_markdown()
            article.summary_model = f"{provider.provider_name}:{getattr(provider, 'model_id', 'unknown')}"

            # 2. Suggest tags
            logger.info(f"Suggesting tags for article {article_id}")
            existing_tags = await self._get_existing_tags(user_id)
            tag_suggestions = await provider.suggest_tags(
                text=article.extracted_text,
                summary=summary.abstract,
                existing_tags=existing_tags,
            )

            # Apply tags
            await self._apply_tags(article, user_id, tag_suggestions)

            # 3. Suggest category
            logger.info(f"Suggesting category for article {article_id}")
            categories = await self._get_category_tree(user_id)
            category_suggestion = await provider.suggest_category(
                text=article.extracted_text,
                summary=summary.abstract,
                categories=categories,
            )

            # Apply category
            await self._apply_category(article, user_id, category_suggestion)

            # 4. Recalculate word count (for reading time)
            if article.extracted_text:
                article.word_count = len(article.extracted_text.split())

            # 5. Generate embedding for semantic search (using local EmbeddingGemma)
            if hasattr(article, 'embedding'):
                logger.info(f"Generating embedding for article {article_id}")
                embedding = self._generate_article_embedding(article)
                if embedding:
                    article.embedding = embedding

            # Mark as completed
            article.processing_status = ProcessingStatus.COMPLETED
            article.processing_error = None

            await self.db.commit()
            await self.db.refresh(article)

            logger.info(f"Successfully processed article {article_id}")
            return article

        except Exception as e:
            logger.error(f"Failed to process article {article_id}: {e}")
            article.processing_status = ProcessingStatus.FAILED
            article.processing_error = str(e)
            await self.db.commit()
            raise

    async def regenerate_summary(
        self,
        article_id: UUID,
        user_id: UUID,
        provider_id: UUID | None = None,
    ) -> Summary:
        """Regenerate just the summary for an article"""
        result = await self.db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if not article:
            raise ValueError(f"Article {article_id} not found")

        # Get provider
        if provider_id:
            provider = await get_ai_provider(self.db, provider_id)
        else:
            provider = await get_default_provider(self.db, user_id)

        if not provider:
            raise ValueError("No AI provider configured")

        source_type = article.source_type.value if hasattr(article.source_type, 'value') else str(article.source_type)
        summary = await provider.summarize(
            text=article.extracted_text,
            title=article.title,
            source_type=source_type,
        )

        article.summary = summary.to_markdown()
        article.summary_model = f"{provider.provider_name}:{getattr(provider, 'model_id', 'unknown')}"

        await self.db.commit()
        return summary

    async def _get_existing_tags(self, user_id: UUID) -> list[str]:
        """Get all existing tag names for a user"""
        result = await self.db.execute(
            select(Tag.name).where(Tag.user_id == user_id)
        )
        return [row[0] for row in result.all()]

    async def _get_category_tree(self, user_id: UUID) -> list[dict]:
        """Get category tree for AI prompt"""
        async def get_children(parent_id: UUID | None) -> list[dict]:
            result = await self.db.execute(
                select(Category)
                .where(
                    Category.user_id == user_id,
                    Category.parent_id == parent_id,
                )
                .order_by(Category.position)
            )
            categories = result.scalars().all()

            tree = []
            for cat in categories:
                children = await get_children(cat.id)
                tree.append({
                    "id": str(cat.id),
                    "name": cat.name,
                    "children": children,
                })
            return tree

        return await get_children(None)

    async def _apply_tags(
        self,
        article: Article,
        user_id: UUID,
        suggestions: list[TagSuggestion],
    ) -> None:
        """Apply tag suggestions to an article"""
        # Only apply tags with confidence >= 0.7
        high_confidence = [s for s in suggestions if s.confidence >= 0.7]

        for suggestion in high_confidence[:7]:  # Max 7 tags
            # Check if tag exists
            result = await self.db.execute(
                select(Tag).where(
                    Tag.user_id == user_id,
                    Tag.name == suggestion.name,
                )
            )
            tag = result.scalar_one_or_none()

            # Create if doesn't exist
            if not tag:
                tag = Tag(
                    user_id=user_id,
                    name=suggestion.name,
                )
                self.db.add(tag)
                await self.db.flush()

            # Check if article-tag association already exists
            existing = await self.db.execute(
                select(ArticleTag).where(
                    ArticleTag.article_id == article.id,
                    ArticleTag.tag_id == tag.id,
                )
            )
            if existing.scalar_one_or_none():
                continue  # Skip if already associated

            # Create article-tag association
            article_tag = ArticleTag(
                article_id=article.id,
                tag_id=tag.id,
                suggested_by_ai=True,
            )
            self.db.add(article_tag)

    async def _apply_category(
        self,
        article: Article,
        user_id: UUID,
        suggestion: CategorySuggestion,
    ) -> None:
        """
        Apply two-level category suggestion to an article.

        Articles are assigned to the SUBCATEGORY only. The parent category
        is just for organizational hierarchy.
        """
        if suggestion.confidence < 0.5:
            logger.info(f"Category suggestion confidence too low ({suggestion.confidence}), skipping")
            return

        # Step 1: Find or create the parent category
        parent_result = await self.db.execute(
            select(Category).where(
                Category.user_id == user_id,
                Category.name == suggestion.category.name,
                Category.parent_id == None,  # Must be a top-level category
            )
        )
        parent_category = parent_result.scalar_one_or_none()

        if not parent_category:
            if suggestion.category.is_new:
                # Create new parent category
                parent_category = Category(
                    user_id=user_id,
                    name=suggestion.category.name,
                    parent_id=None,
                )
                self.db.add(parent_category)
                await self.db.flush()
                logger.info(f"Created new category: {suggestion.category.name}")
            else:
                # Parent should exist but doesn't - log and create anyway to avoid data loss
                logger.warning(f"Category '{suggestion.category.name}' not found, creating it")
                parent_category = Category(
                    user_id=user_id,
                    name=suggestion.category.name,
                    parent_id=None,
                )
                self.db.add(parent_category)
                await self.db.flush()

        # Step 2: Find or create the subcategory under the parent
        subcategory_result = await self.db.execute(
            select(Category).where(
                Category.user_id == user_id,
                Category.name == suggestion.subcategory.name,
                Category.parent_id == parent_category.id,
            )
        )
        subcategory = subcategory_result.scalar_one_or_none()

        if not subcategory:
            if suggestion.subcategory.is_new:
                # Create new subcategory
                subcategory = Category(
                    user_id=user_id,
                    name=suggestion.subcategory.name,
                    parent_id=parent_category.id,
                )
                self.db.add(subcategory)
                await self.db.flush()
                logger.info(f"Created new subcategory: {suggestion.category.name} → {suggestion.subcategory.name}")
            else:
                # Subcategory should exist but doesn't - create it anyway
                logger.warning(f"Subcategory '{suggestion.subcategory.name}' not found under '{suggestion.category.name}', creating it")
                subcategory = Category(
                    user_id=user_id,
                    name=suggestion.subcategory.name,
                    parent_id=parent_category.id,
                )
                self.db.add(subcategory)
                await self.db.flush()

        # Step 3: Remove any existing category assignments for this article
        # This prevents double-counting when re-analyzing or changing categories
        await self.db.execute(
            delete(ArticleCategory).where(ArticleCategory.article_id == article.id)
        )

        # Step 4: Assign article to the subcategory (not the parent)
        article_category = ArticleCategory(
            article_id=article.id,
            category_id=subcategory.id,
            is_primary=True,
            suggested_by_ai=True,
        )
        self.db.add(article_category)
        logger.info(f"Assigned article to: {suggestion.category.name} → {suggestion.subcategory.name}")

    def _generate_article_embedding(
        self,
        article: Article,
    ) -> list[float] | None:
        """
        Generate embedding for an article using local EmbeddingGemma model.

        Combines title, summary, and content into a single text for embedding.
        This captures both the high-level topic and detailed content.
        """
        # Build text to embed: title + summary + content excerpt
        parts = []

        if article.title:
            parts.append(f"Title: {article.title}")

        if article.summary:
            # Include full summary (it's already condensed)
            parts.append(f"Summary: {article.summary}")

        if article.extracted_text:
            # Include first ~4000 chars of content (within embedding limits)
            content_excerpt = article.extracted_text[:4000]
            parts.append(f"Content: {content_excerpt}")

        if not parts:
            logger.warning(f"No content to embed for article {article.id}")
            return None

        text_to_embed = "\n\n".join(parts)

        try:
            embedding = generate_embedding(text_to_embed)
            if embedding:
                logger.info(f"Generated embedding ({len(embedding)} dims) for article {article.id}")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding for article {article.id}: {e}")
            return None
