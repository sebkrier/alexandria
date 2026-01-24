"""Data fetching helpers for HTMX routes."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_category import ArticleCategory
from app.models.category import Category
from app.models.color import Color
from app.models.tag import Tag


async def fetch_sidebar_data(db: AsyncSession, user_id: UUID) -> dict:
    """Fetch all data needed for the sidebar."""
    categories = await fetch_categories_with_counts(db, user_id)
    colors = await fetch_colors(db, user_id)
    unread_count = await fetch_unread_count(db, user_id)

    return {
        "categories": categories,
        "colors": colors,
        "unread_count": unread_count,
    }


async def fetch_categories_with_counts(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Fetch categories with article counts, organized in a tree structure."""
    # Get all categories for user
    result = await db.execute(
        select(Category)
        .where(Category.user_id == user_id)
        .order_by(Category.position, Category.name)
    )
    categories = result.scalars().all()

    # Get article counts per category (direct counts only)
    count_result = await db.execute(
        select(ArticleCategory.category_id, func.count(ArticleCategory.article_id))
        .join(Article, Article.id == ArticleCategory.article_id)
        .where(Article.user_id == user_id)
        .group_by(ArticleCategory.category_id)
    )
    direct_counts = {row[0]: row[1] for row in count_result.all()}

    # Build tree structure with recursive counts
    def build_tree(parent_id: UUID | None) -> list[dict]:
        children = []
        for cat in categories:
            if cat.parent_id == parent_id:
                child_nodes = build_tree(cat.id)
                # Sum direct count + all descendant counts
                direct_count = direct_counts.get(cat.id, 0)
                descendant_count = sum(c["article_count"] for c in child_nodes)
                children.append(
                    {
                        "id": str(cat.id),
                        "name": cat.name,
                        "article_count": direct_count + descendant_count,
                        "children": child_nodes,
                    }
                )
        return children

    return build_tree(None)


async def fetch_colors(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Fetch all colors for user."""
    result = await db.execute(
        select(Color).where(Color.user_id == user_id).order_by(Color.position, Color.name)
    )
    colors = result.scalars().all()

    return [
        {
            "id": str(color.id),
            "name": color.name,
            "hex_value": color.hex_value,
        }
        for color in colors
    ]


async def fetch_tags(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Fetch all tags for user."""
    result = await db.execute(select(Tag).where(Tag.user_id == user_id).order_by(Tag.name))
    tags = result.scalars().all()

    return [
        {
            "id": str(tag.id),
            "name": tag.name,
            "color": tag.color,
        }
        for tag in tags
    ]


async def fetch_unread_count(db: AsyncSession, user_id: UUID) -> int:
    """Count unread articles (is_read == False)."""
    result = await db.execute(
        select(func.count(Article.id)).where(Article.user_id == user_id, Article.is_read.is_(False))
    )
    return result.scalar() or 0
