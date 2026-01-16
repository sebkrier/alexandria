"""
HTMX Routes - HTML pages served by FastAPI with Jinja2 templates.

These routes return HTML instead of JSON, and are used by the HTMX frontend.
The JSON API routes in /api/* remain unchanged for backwards compatibility.
"""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.article import Article, ProcessingStatus, SourceType
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.category import Category
from app.models.color import Color
from app.models.user import User
from app.schemas.article import MediaType
from app.utils.auth import get_current_user

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Helper functions for converting models to template-friendly dicts
# =============================================================================


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
            "medium.com", "dev.to", "hashnode.", "wordpress.com",
            "/blog/", ".blog.", "blogger.com", "ghost.io",
        ]
        if any(indicator in url_lower for indicator in blog_indicators):
            return "blog"

        paper_indicators = [
            "arxiv.org", "doi.org", "nature.com", "science.org",
            "ieee.org", "acm.org", "springer.com", "wiley.com",
            "researchgate.net", "semanticscholar.org", ".edu/",
            "pubmed", "ncbi.nlm.nih.gov",
        ]
        if any(indicator in url_lower for indicator in paper_indicators):
            return "paper"

    return "article"


def article_to_dict(article: Article) -> dict:
    """Convert Article model to a dict for templates"""
    categories = []
    for ac in article.categories:
        categories.append({
            "id": str(ac.category.id),
            "name": ac.category.name,
            "is_primary": ac.is_primary,
        })

    tags = []
    for at in article.tags:
        tags.append({
            "id": str(at.tag.id),
            "name": at.tag.name,
            "color": at.tag.color,
        })

    color = None
    if article.color:
        color = {
            "id": str(article.color.id),
            "hex_value": article.color.hex_value,
            "name": article.color.name,
        }

    # Handle source_type - might be enum or string
    source_type_val = article.source_type
    if hasattr(source_type_val, 'value'):
        source_type_str = source_type_val.value
    else:
        source_type_str = str(source_type_val) if source_type_val else "url"

    # Handle processing_status - might be enum or string
    proc_status = article.processing_status
    if hasattr(proc_status, 'value'):
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


# =============================================================================
# Sidebar data helpers
# =============================================================================


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

    # Get article counts per category
    count_result = await db.execute(
        select(ArticleCategory.category_id, func.count(ArticleCategory.article_id))
        .join(Article, Article.id == ArticleCategory.article_id)
        .where(Article.user_id == user_id)
        .group_by(ArticleCategory.category_id)
    )
    counts = {row[0]: row[1] for row in count_result.all()}

    # Build tree structure
    def build_tree(parent_id: UUID | None) -> list[dict]:
        children = []
        for cat in categories:
            if cat.parent_id == parent_id:
                children.append({
                    "id": str(cat.id),
                    "name": cat.name,
                    "article_count": counts.get(cat.id, 0),
                    "children": build_tree(cat.id),
                })
        return children

    return build_tree(None)


async def fetch_colors(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Fetch all colors for user."""
    result = await db.execute(
        select(Color)
        .where(Color.user_id == user_id)
        .order_by(Color.position, Color.name)
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


async def fetch_unread_count(db: AsyncSession, user_id: UUID) -> int:
    """Count unread articles."""
    result = await db.execute(
        select(func.count(Article.id))
        .where(Article.user_id == user_id, Article.is_read == False)  # noqa: E712
    )
    return result.scalar() or 0


# =============================================================================
# Main Application Routes
# =============================================================================


@router.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    search: str | None = None,
    view: str = "grid",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: UUID | None = None,
    color_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Main article list page."""
    # Fetch articles
    articles, total = await fetch_articles(
        db=db,
        user_id=current_user.id,
        search=search,
        page=page,
        page_size=page_size,
        category_id=category_id,
        color_id=color_id,
    )

    total_pages = (total + page_size - 1) // page_size

    # Fetch sidebar data
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="pages/index.html",
        context={
            "articles": [article_to_dict(a) for a in articles],
            "view_mode": view,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "search": search,
            "current_path": str(request.url.path),
            "selected_category_id": str(category_id) if category_id else None,
            "selected_color_id": str(color_id) if color_id else None,
            **sidebar_data,
        },
    )


@router.get("/articles", response_class=HTMLResponse)
async def articles_partial(
    request: Request,
    search: str | None = None,
    view: str = "grid",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: UUID | None = None,
    tag_id: UUID | None = None,
    color_id: UUID | None = None,
    is_read: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Article list partial for HTMX requests."""
    # Fetch articles
    articles, total = await fetch_articles(
        db=db,
        user_id=current_user.id,
        search=search,
        page=page,
        page_size=page_size,
        category_id=category_id,
        tag_id=tag_id,
        color_id=color_id,
        is_read=is_read,
    )

    total_pages = (total + page_size - 1) // page_size

    # Check if this is an HTMX request
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        # Return just the article list partial
        return templates.TemplateResponse(
            request=request,
            name="partials/article_list.html",
            context={
                "articles": [article_to_dict(a) for a in articles],
                "view_mode": view,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "search": search,
            },
        )
    else:
        # Return full page (for direct navigation)
        sidebar_data = await fetch_sidebar_data(db, current_user.id)
        return templates.TemplateResponse(
            request=request,
            name="pages/index.html",
            context={
                "articles": [article_to_dict(a) for a in articles],
                "view_mode": view,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "search": search,
                "current_path": str(request.url.path),
                "selected_category_id": str(category_id) if category_id else None,
                "selected_color_id": str(color_id) if color_id else None,
                **sidebar_data,
            },
        )


async def fetch_articles(
    db: AsyncSession,
    user_id: UUID,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    category_id: UUID | None = None,
    tag_id: UUID | None = None,
    color_id: UUID | None = None,
    is_read: bool | None = None,
) -> tuple[list[Article], int]:
    """Fetch articles with filtering and pagination."""
    # Base query with eager loading
    query = (
        select(Article)
        .where(Article.user_id == user_id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.color),
        )
    )

    # Apply filters
    if search:
        query = query.where(
            or_(
                Article.title.ilike(f"%{search}%"),
                Article.search_vector.match(search),
            )
        )

    if category_id:
        async def get_descendant_ids(cat_id: UUID) -> list[UUID]:
            result = await db.execute(select(Category.id).where(Category.parent_id == cat_id))
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

    if is_read is not None:
        query = query.where(Article.is_read == is_read)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination and ordering
    query = query.order_by(Article.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    articles = result.scalars().all()

    return list(articles), total


# =============================================================================
# Test Routes (for development)
# =============================================================================


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail_page(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Article detail page."""
    from app.models.note import Note

    # Fetch article with all relationships
    query = (
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.color),
        )
    )
    result = await db.execute(query)
    article = result.scalar_one_or_none()

    if not article:
        return templates.TemplateResponse(
            request=request,
            name="pages/not_found.html",
            context={"message": "Article not found"},
            status_code=404,
        )

    # Fetch notes for this article
    notes_query = (
        select(Note)
        .where(Note.article_id == article_id)
        .order_by(Note.created_at.desc())
    )
    notes_result = await db.execute(notes_query)
    notes = notes_result.scalars().all()

    # Convert article to template-friendly dict
    article_dict = article_to_detail_dict(article)
    article_dict["notes"] = [
        {
            "id": str(note.id),
            "content": note.content,
            "created_at": note.created_at,
        }
        for note in notes
    ]

    return templates.TemplateResponse(
        request=request,
        name="pages/article.html",
        context={"article": article_dict},
    )


def article_to_detail_dict(article: Article) -> dict:
    """Convert Article model to a detailed dict for article detail template."""
    categories = []
    for ac in article.categories:
        categories.append({
            "id": str(ac.category.id),
            "name": ac.category.name,
            "is_primary": ac.is_primary,
        })

    tags = []
    for at in article.tags:
        tags.append({
            "id": str(at.tag.id),
            "name": at.tag.name,
            "color": at.tag.color,
        })

    color = None
    if article.color:
        color = {
            "id": str(article.color.id),
            "hex_value": article.color.hex_value,
            "name": article.color.name,
        }

    # Handle source_type - might be enum or string
    source_type_val = article.source_type
    if hasattr(source_type_val, 'value'):
        source_type_str = source_type_val.value
    else:
        source_type_str = str(source_type_val) if source_type_val else "url"

    # Handle processing_status - might be enum or string
    proc_status = article.processing_status
    if hasattr(proc_status, 'value'):
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
        "summary_model": article.summary_model,
        "is_read": article.is_read,
        "reading_time_minutes": calculate_reading_time(article.word_count),
        "processing_status": proc_status_str,
        "processing_error": article.processing_error,
        "publication_date": article.publication_date,
        "color": color,
        "categories": categories,
        "tags": tags,
        "created_at": article.created_at,
    }


# =============================================================================
# Test Routes (for development)
# =============================================================================


@router.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """Test page to verify HTMX + Jinja2 setup is working."""
    return templates.TemplateResponse(
        request=request,
        name="pages/test.html",
        context={
            "title": "HTMX Test Page",
            "message": "If you can see this, HTMX + Jinja2 is working!",
            "features": [
                "Tailwind CSS via CDN",
                "HTMX for dynamic updates",
                "Alpine.js for client state",
                "Dark mode styling",
            ],
        },
    )


@router.get("/test/click", response_class=HTMLResponse)
async def test_click(request: Request):
    """Partial response for HTMX click test."""
    import random  # noqa: S311

    colors = [
        "text-article-blue",
        "text-article-green",
        "text-article-orange",
        "text-article-purple",
        "text-article-red",
    ]
    color = random.choice(colors)  # noqa: S311
    return f'<span class="{color} font-bold">Button clicked! HTMX is working.</span>'


# Mock article data for testing
MOCK_ARTICLES = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "title": "Understanding Large Language Models: A Comprehensive Guide",
        "source_type": "url",
        "media_type": "article",
        "original_url": "https://example.com/llm-guide",
        "summary": """Large language models (LLMs) have revolutionized natural language processing.

This guide explores the architecture, training methods, and applications of modern LLMs like GPT-4 and Claude.

## Key Concepts
- Transformer architecture
- Attention mechanisms
- Fine-tuning strategies""",
        "is_read": False,
        "reading_time_minutes": 12,
        "processing_status": "completed",
        "color": {"hex_value": "#6B7FD7"},
        "categories": [{"id": "cat1", "name": "AI/ML"}],
        "tags": [
            {"id": "tag1", "name": "LLM", "color": "#8B5CF6"},
            {"id": "tag2", "name": "Research", "color": "#10B981"},
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "title": "Attention Is All You Need - The Paper That Changed NLP",
        "source_type": "arxiv",
        "media_type": "paper",
        "original_url": "https://arxiv.org/abs/1706.03762",
        "summary": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism.",
        "is_read": True,
        "reading_time_minutes": 45,
        "processing_status": "completed",
        "color": None,
        "categories": [{"id": "cat2", "name": "Papers"}],
        "tags": [
            {"id": "tag3", "name": "Transformers", "color": "#F59E0B"},
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "title": "Building Production ML Systems - Stanford CS229",
        "source_type": "video",
        "media_type": "video",
        "original_url": "https://youtube.com/watch?v=example",
        "summary": "Learn how to build and deploy machine learning systems in production environments.",
        "is_read": False,
        "reading_time_minutes": 90,
        "processing_status": "processing",
        "color": {"hex_value": "#D4915D"},
        "categories": [],
        "tags": [
            {"id": "tag4", "name": "MLOps", "color": "#EC4899"},
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "title": "The State of AI in 2024",
        "source_type": "pdf",
        "media_type": "pdf",
        "original_url": None,
        "summary": None,
        "is_read": False,
        "reading_time_minutes": None,
        "processing_status": "pending",
        "color": {"hex_value": "#D46A6A"},
        "categories": [{"id": "cat3", "name": "Reports"}],
        "tags": [],
    },
]


@router.get("/test/card", response_class=HTMLResponse)
async def test_card(request: Request, view: str = "grid"):
    """Test page to preview article cards with mock data."""
    return templates.TemplateResponse(
        request=request,
        name="pages/test_cards.html",
        context={
            "title": "Article Card Test",
            "articles": MOCK_ARTICLES,
            "view_mode": view,
        },
    )
