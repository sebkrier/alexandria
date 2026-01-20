from pathlib import Path
from uuid import UUID

from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, SourceType
from app.models.article_category import ArticleCategory
from app.models.category import Category
from app.models.color import Color
from app.models.tag import Tag

# Template configuration
# Assuming backend/app/api/htmx/utils.py, templates is at backend/templates
# ../../../templates
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

def calculate_reading_time(word_count: int | None) -> int | None:
    """Calculate reading time in minutes (200 words per minute)"""
    if word_count is None:
        return None
    return max(1, round(word_count / 200))


def determine_media_type(source_type: SourceType, original_url: str | None) -> str:
    """Determine user-friendly media type from source_type and URL"""
    if source_type == SourceType.ARXIV:
        return "paper"
    if source_type == SourceType.VIDEO:
        return "video"
    if source_type == SourceType.PDF:
        return "pdf"

    if source_type == SourceType.URL and original_url:
        url_lower = original_url.lower()

        if "substack.com" in url_lower or "/p/" in url_lower:
            return "newsletter"

        blog_indicators = [
            "medium.com",
            "dev.to",
            "hashnode.",
            "wordpress.com",
            "/blog/",
            ".blog.",
            "blogger.com",
            "ghost.io",
        ]
        if any(indicator in url_lower for indicator in blog_indicators):
            return "blog"

        paper_indicators = [
            "arxiv.org",
            "doi.org",
            "nature.com",
            "science.org",
            "ieee.org",
            "acm.org",
            "springer.com",
            "wiley.com",
            "researchgate.net",
            "semanticscholar.org",
            ".edu/",
            "pubmed",
            "ncbi.nlm.nih.gov",
        ]
        if any(indicator in url_lower for indicator in paper_indicators):
            return "paper"

    return "article"


def article_to_dict(article: Article) -> dict:
    """Convert Article model to a dict for templates"""
    categories = []
    if article.categories:
        for ac in article.categories:
            categories.append(
                {
                    "id": str(ac.category.id),
                    "name": ac.category.name,
                    "is_primary": ac.is_primary,
                }
            )

    tags = []
    if article.tags:
        for at in article.tags:
            tags.append(
                {
                    "id": str(at.tag.id),
                    "name": at.tag.name,
                    "color": at.tag.color,
                }
            )

    color = None
    if article.color:
        color = {
            "id": str(article.color.id),
            "hex_value": article.color.hex_value,
            "name": article.color.name,
        }

    # Handle source_type - might be enum or string
    source_type_val = article.source_type
    if hasattr(source_type_val, "value"):
        source_type_str = source_type_val.value
    else:
        source_type_str = str(source_type_val) if source_type_val else "url"

    # Handle processing_status - might be enum or string
    proc_status = article.processing_status
    if hasattr(proc_status, "value"):
        proc_status_str = proc_status.value
    else:
        proc_status_str = str(proc_status) if proc_status else "pending"

    return {
        "id": str(article.id),
        "source_type": source_type_str,
        "media_type": determine_media_type(article.source_type, article.original_url),
        "original_url": article.original_url,
        "title": article.title or "Untitled",
        "authors": article.authors or [],
        "summary": article.summary,
        "is_read": article.is_read,
        "reading_time_minutes": calculate_reading_time(article.word_count),
        "processing_status": proc_status_str,
        "color": color,
        "categories": categories,
        "tags": tags,
        "created_at": article.created_at,
    }

def article_to_detail_dict(article: Article) -> dict:
    """Convert Article model to a detailed dict for article detail template."""
    categories = []
    if article.categories:
        for ac in article.categories:
            categories.append(
                {
                    "id": str(ac.category.id),
                    "name": ac.category.name,
                    "is_primary": ac.is_primary,
                }
            )

    tags = []
    if article.tags:
        for at in article.tags:
            tags.append(
                {
                    "id": str(at.tag.id),
                    "name": at.tag.name,
                    "color": at.tag.color,
                }
            )

    color = None
    if article.color:
        color = {
            "id": str(article.color.id),
            "hex_value": article.color.hex_value,
            "name": article.color.name,
        }

    # Handle source_type - might be enum or string
    source_type_val = article.source_type
    if hasattr(source_type_val, "value"):
        source_type_str = source_type_val.value
    else:
        source_type_str = str(source_type_val) if source_type_val else "url"

    # Handle processing_status - might be enum or string
    proc_status = article.processing_status
    if hasattr(proc_status, "value"):
        proc_status_str = proc_status.value
    else:
        proc_status_str = str(proc_status) if proc_status else "pending"

    # Include notes if loaded (check if relationship is actually loaded to avoid lazy load in async)
    notes = []
    # Using simple check if populated
    if 'notes' in article.__dict__:
        for note in sorted(article.notes, key=lambda n: n.created_at, reverse=True):
            notes.append(
                {
                    "id": str(note.id),
                    "content": note.content,
                    "created_at": note.created_at,
                }
            )

    return {
        "id": str(article.id),
        "source_type": source_type_str,
        "media_type": determine_media_type(article.source_type, article.original_url),
        "original_url": article.original_url,
        "title": article.title or "Untitled",
        "authors": article.authors or [],
        "summary": article.summary,
        "summary_model": article.summary_model,
        "is_read": article.is_read,
        "reading_time_minutes": calculate_reading_time(article.word_count),
        "processing_status": proc_status_str,
        "processing_error": article.processing_error,
        "publication_date": article.publication_date,
        "color": color,
        "categories": categories,
        "tags": tags,
        "notes": notes,
        "created_at": article.created_at,
    }

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
        select(func.count(Article.id)).where(Article.user_id == user_id, Article.is_read == False)
    )
    return result.scalar() or 0
