"""
HTMX Routes - HTML pages served by FastAPI with Jinja2 templates.

These routes return HTML instead of JSON, and are used by the HTMX frontend.
The JSON API routes in /api/* remain unchanged for backwards compatibility.
"""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
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
from app.models.tag import Tag
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
                children.append({
                    "id": str(cat.id),
                    "name": cat.name,
                    "article_count": direct_count + descendant_count,
                    "children": child_nodes,
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


async def fetch_tags(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Fetch all tags for user."""
    result = await db.execute(
        select(Tag)
        .where(Tag.user_id == user_id)
        .order_by(Tag.name)
    )
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
        select(func.count(Article.id))
        .where(Article.user_id == user_id, Article.is_read == False)
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
            "colors": sidebar_data.get("colors", []),  # For bulk action bar color picker
            **sidebar_data,
        },
    )


@router.get("/articles", response_class=HTMLResponse)
async def articles_partial(
    request: Request,
    search: str | None = None,
    view: str = "grid",
    category_id: UUID | None = None,
    tag_id: UUID | None = None,
    color_id: UUID | None = None,
    is_read: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Article list partial for HTMX requests. Returns all articles (no pagination)."""
    # Fetch all articles (no pagination)
    articles, total = await fetch_articles(
        db=db,
        user_id=current_user.id,
        search=search,
        page=1,
        page_size=10000,  # Effectively no limit
        category_id=category_id,
        tag_id=tag_id,
        color_id=color_id,
        is_read=is_read,
    )

    # Check if this is an HTMX request
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        return templates.TemplateResponse(
            request=request,
            name="partials/article_list.html",
            context={
                "articles": [article_to_dict(a) for a in articles],
                "view_mode": view,
                "total": total,
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

    # Fetch colors for the color picker
    colors = await fetch_colors(db, current_user.id)

    # Fetch all categories for category editing
    all_categories = await fetch_categories_with_counts(db, current_user.id)

    # Fetch all tags for tag editing
    all_tags = await fetch_tags(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="pages/article.html",
        context={
            "article": article_dict,
            "colors": colors,
            "all_categories": all_categories,
            "all_tags": all_tags,
        },
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


@router.delete("/article/{article_id}", response_class=HTMLResponse)
async def delete_article(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a single article via HTMX."""
    # Verify article exists and belongs to user
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Article not found",
            },
        )

    title = article.title or "Untitled"

    # Delete the article (cascade handles notes, tags, categories)
    await db.delete(article)
    await db.commit()

    # Return redirect to library with success toast
    response = templates.TemplateResponse(
        request=request,
        name="components/toast.html",
        context={
            "toast_type": "success",
            "toast_message": f"Deleted: {title[:40]}{'...' if len(title) > 40 else ''}",
        },
    )
    response.headers["HX-Redirect"] = "/app/"
    return response


# =============================================================================
# Article Edit Routes (HTMX)
# =============================================================================


@router.patch("/article/{article_id}/color", response_class=HTMLResponse)
async def update_article_color(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update article color via HTMX."""
    form = await request.form()
    color_id_str = form.get("color_id")
    color_id = UUID(color_id_str) if color_id_str else None

    # Fetch article
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
        .options(selectinload(Article.color))
    )
    article = result.scalar_one_or_none()

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

    # Update color
    article.color_id = color_id
    await db.commit()

    # Fetch updated color info
    color_info = None
    if color_id:
        color_result = await db.execute(
            select(Color).where(Color.id == color_id)
        )
        color = color_result.scalar_one_or_none()
        if color:
            color_info = {
                "id": str(color.id),
                "hex_value": color.hex_value,
                "name": color.name,
            }

    # Fetch all colors for the picker
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/article_color_section.html",
        context={
            "article": {"id": str(article_id), "color": color_info},
            "colors": colors,
        },
    )


@router.patch("/article/{article_id}/categories", response_class=HTMLResponse)
async def update_article_categories(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update article categories via HTMX."""
    from sqlalchemy import delete

    form = await request.form()
    # Get all category_ids from form (checkboxes send multiple values)
    category_ids = form.getlist("category_ids")

    # Fetch article
    result = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

    # Remove existing categories
    await db.execute(
        delete(ArticleCategory).where(ArticleCategory.article_id == article_id)
    )

    # Add new categories
    for i, cat_id_str in enumerate(category_ids):
        cat_id = UUID(cat_id_str)
        ac = ArticleCategory(
            article_id=article_id,
            category_id=cat_id,
            is_primary=(i == 0),
        )
        db.add(ac)

    await db.commit()

    # Fetch updated categories
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.categories).selectinload(ArticleCategory.category))
    )
    article = result.scalar_one()

    categories = [
        {"id": str(ac.category.id), "name": ac.category.name, "is_primary": ac.is_primary}
        for ac in article.categories
    ]

    # Fetch all categories for the picker
    all_categories = await fetch_categories_with_counts(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/article_categories_section.html",
        context={
            "article": {"id": str(article_id), "categories": categories},
            "all_categories": all_categories,
        },
    )


@router.patch("/article/{article_id}/tags", response_class=HTMLResponse)
async def update_article_tags(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update article tags via HTMX."""
    from sqlalchemy import delete

    form = await request.form()
    # Get all tag_ids from form (checkboxes send multiple values)
    tag_ids = form.getlist("tag_ids")

    # Fetch article
    result = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

    # Remove existing tags
    await db.execute(
        delete(ArticleTag).where(ArticleTag.article_id == article_id)
    )

    # Add new tags
    for tag_id_str in tag_ids:
        tag_id = UUID(tag_id_str)
        at = ArticleTag(
            article_id=article_id,
            tag_id=tag_id,
        )
        db.add(at)

    await db.commit()

    # Fetch updated tags
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.tags).selectinload(ArticleTag.tag))
    )
    article = result.scalar_one()

    tags = [
        {"id": str(at.tag.id), "name": at.tag.name, "color": at.tag.color}
        for at in article.tags
    ]

    # Fetch all tags for the picker
    all_tags = await fetch_tags(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/article_tags_section.html",
        context={
            "article": {"id": str(article_id), "tags": tags},
            "all_tags": all_tags,
        },
    )


@router.post("/article/{article_id}/notes", response_class=HTMLResponse)
async def create_article_note(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a note for an article via HTMX."""
    from app.models.note import Note

    form = await request.form()
    content = form.get("content", "").strip()

    if not content:
        return HTMLResponse("<div>Note content is required</div>", status_code=400)

    # Verify article belongs to user
    result = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

    # Create note
    note = Note(article_id=article_id, content=content)
    db.add(note)
    await db.commit()
    await db.refresh(note)

    # Fetch all notes for this article
    notes_result = await db.execute(
        select(Note)
        .where(Note.article_id == article_id)
        .order_by(Note.created_at.desc())
    )
    notes = notes_result.scalars().all()

    notes_list = [
        {"id": str(n.id), "content": n.content, "created_at": n.created_at}
        for n in notes
    ]

    return templates.TemplateResponse(
        request=request,
        name="partials/article_notes_section.html",
        context={
            "article": {"id": str(article_id), "notes": notes_list},
        },
    )


@router.post("/article/{article_id}/reprocess", response_class=HTMLResponse)
async def reprocess_article(
    request: Request,
    article_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reprocess an article (regenerate summary and categories) via HTMX."""
    from app.database import async_session_maker

    # Fetch article
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Article not found",
            },
        )

    # Skip if already processing
    if article.processing_status == ProcessingStatus.PROCESSING:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "warning",
                "toast_message": "Article is already being processed",
            },
        )

    # Mark as processing immediately for better UX
    article.processing_status = ProcessingStatus.PROCESSING
    article.processing_error = None
    await db.commit()

    # Schedule background processing
    async def process_in_background(aid: UUID, uid: UUID):
        async with async_session_maker() as bg_db:
            try:
                from app.ai.service import AIService
                ai_service = AIService(bg_db)
                logging.info(f"Starting background reprocess for article {aid}")
                await ai_service.process_article(article_id=aid, user_id=uid)
                logging.info(f"Background reprocess completed for article {aid}")
            except Exception as e:
                logging.error(f"Background reprocessing failed for {aid}: {e}", exc_info=True)
                # Update article status to failed
                try:
                    result = await bg_db.execute(
                        select(Article).where(Article.id == aid)
                    )
                    article = result.scalar_one_or_none()
                    if article:
                        article.processing_status = ProcessingStatus.FAILED
                        article.processing_error = str(e)
                        await bg_db.commit()
                except Exception as update_err:
                    logging.error(f"Failed to update article status: {update_err}")

    background_tasks.add_task(process_in_background, article_id, current_user.id)

    # Return toast + OOB swap for processing banner
    toast_html = templates.get_template("components/toast.html").render({
        "toast_type": "success",
        "toast_message": f"Re-analyzing: {article.title[:40]}{'...' if len(article.title or '') > 40 else ''}",
    })

    # Build processing banner HTML with polling to check status
    processing_banner = f'''
    <div id="processing-status-banner" hx-swap-oob="outerHTML"
         hx-get="/app/article/{article_id}/status"
         hx-trigger="every 2s"
         hx-swap="outerHTML">
        <div class="mb-6 p-4 rounded-lg border bg-article-blue/10 border-article-blue/30">
            <div class="flex items-center gap-3">
                <svg class="w-5 h-5 text-article-blue animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <div>
                    <p class="font-medium text-white">Processing...</p>
                </div>
            </div>
        </div>
    </div>
    '''

    return HTMLResponse(content=toast_html + processing_banner)


@router.get("/article/{article_id}/status", response_class=HTMLResponse)
async def get_article_processing_status(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get article processing status - used for polling during reprocessing."""
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        return HTMLResponse("<div id='processing-status-banner'></div>")

    status = article.processing_status.value if hasattr(article.processing_status, 'value') else str(article.processing_status)

    # If still processing, return banner with polling
    if status == 'processing':
        return HTMLResponse(f'''
        <div id="processing-status-banner"
             hx-get="/app/article/{article_id}/status"
             hx-trigger="every 2s"
             hx-swap="outerHTML">
            <div class="mb-6 p-4 rounded-lg border bg-article-blue/10 border-article-blue/30">
                <div class="flex items-center gap-3">
                    <svg class="w-5 h-5 text-article-blue animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <div>
                        <p class="font-medium text-white">Processing...</p>
                    </div>
                </div>
            </div>
        </div>
        ''')

    # If failed, show error
    if status == 'failed':
        error_msg = article.processing_error or "Unknown error"
        return HTMLResponse(f'''
        <div id="processing-status-banner">
            <div class="mb-6 p-4 rounded-lg border bg-article-red/10 border-article-red/30">
                <div class="flex items-center gap-3">
                    <svg class="w-5 h-5 text-article-red" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <circle cx="12" cy="12" r="10" stroke-width="2"></circle>
                        <line x1="12" y1="8" x2="12" y2="12" stroke-width="2"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16" stroke-width="2"></line>
                    </svg>
                    <div>
                        <p class="font-medium text-white">Processing failed</p>
                        <p class="text-sm text-dark-muted mt-1">{error_msg}</p>
                    </div>
                </div>
            </div>
        </div>
        ''')

    # Completed - show success briefly then trigger page refresh
    return HTMLResponse(f'''
    <div id="processing-status-banner">
        <div class="mb-6 p-4 rounded-lg border bg-article-green/10 border-article-green/30">
            <div class="flex items-center gap-3">
                <svg class="w-5 h-5 text-article-green" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                <div>
                    <p class="font-medium text-white">Processing complete!</p>
                    <p class="text-sm text-dark-muted mt-1">Refreshing page...</p>
                </div>
            </div>
        </div>
    </div>
    <script>setTimeout(function() {{ window.location.reload(); }}, 1000);</script>
    ''')


@router.delete("/article/{article_id}/notes/{note_id}", response_class=HTMLResponse)
async def delete_article_note(
    request: Request,
    article_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note via HTMX."""
    from app.models.note import Note

    # Verify note belongs to user's article
    result = await db.execute(
        select(Note)
        .join(Article)
        .where(Note.id == note_id, Article.user_id == current_user.id)
    )
    note = result.scalar_one_or_none()

    if not note:
        return HTMLResponse("<div>Note not found</div>", status_code=404)

    await db.delete(note)
    await db.commit()

    # Fetch remaining notes
    notes_result = await db.execute(
        select(Note)
        .where(Note.article_id == article_id)
        .order_by(Note.created_at.desc())
    )
    notes = notes_result.scalars().all()

    notes_list = [
        {"id": str(n.id), "content": n.content, "created_at": n.created_at}
        for n in notes
    ]

    return templates.TemplateResponse(
        request=request,
        name="partials/article_notes_section.html",
        context={
            "article": {"id": str(article_id), "notes": notes_list},
        },
    )


# =============================================================================
# Settings Routes
# =============================================================================


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Settings page with AI providers and colors."""
    from app.ai.factory import get_available_providers
    from app.ai.prompts import EXTRACT_SUMMARY_PROMPT, SUMMARY_SYSTEM_PROMPT
    from app.models.ai_provider import AIProvider as AIProviderModel
    from app.utils.encryption import decrypt_api_key, mask_api_key

    # Fetch providers
    result = await db.execute(
        select(AIProviderModel)
        .where(AIProviderModel.user_id == current_user.id)
        .order_by(AIProviderModel.created_at)
    )
    provider_models = result.scalars().all()

    providers = []
    for p in provider_models:
        api_key = decrypt_api_key(p.api_key_encrypted)
        providers.append({
            "id": str(p.id),
            "provider_name": p.provider_name.value if hasattr(p.provider_name, 'value') else str(p.provider_name),
            "display_name": p.display_name,
            "model_id": p.model_id,
            "api_key_masked": mask_api_key(api_key),
            "is_default": p.is_default,
            "is_active": p.is_active,
        })

    # Fetch colors
    colors = await fetch_colors(db, current_user.id)

    # Fetch sidebar data
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    # Get available providers info
    available_providers = get_available_providers()

    # Get prompts
    prompts = {
        "system_prompt": SUMMARY_SYSTEM_PROMPT,
        "user_prompt": EXTRACT_SUMMARY_PROMPT,
    }

    return templates.TemplateResponse(
        request=request,
        name="pages/settings.html",
        context={
            "providers": providers,
            "available_providers": available_providers,
            "colors": colors,
            "prompts": prompts,
            "current_path": "/app/settings",
            **sidebar_data,
        },
    )


@router.get("/modals/add-provider", response_class=HTMLResponse)
async def add_provider_modal(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the add provider modal HTML."""
    from app.ai.factory import get_available_providers

    available_providers = get_available_providers()

    return templates.TemplateResponse(
        request=request,
        name="modals/add_provider.html",
        context={
            "available_providers": available_providers,
        },
    )


@router.post("/settings/providers", response_class=HTMLResponse)
async def create_provider(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new AI provider."""
    from app.models.ai_provider import AIProvider as AIProviderModel
    from app.models.ai_provider import ProviderName
    from app.utils.encryption import decrypt_api_key, encrypt_api_key, mask_api_key

    form = await request.form()
    provider_name = form.get("provider_name")
    display_name = form.get("display_name")
    model_id = form.get("model_id")
    api_key = form.get("api_key")

    # Check if this is the first provider
    result = await db.execute(
        select(AIProviderModel).where(AIProviderModel.user_id == current_user.id).limit(1)
    )
    is_first = result.scalar_one_or_none() is None

    # Encrypt API key
    encrypted_key = encrypt_api_key(api_key)

    provider = AIProviderModel(
        user_id=current_user.id,
        provider_name=ProviderName(provider_name),
        display_name=display_name,
        model_id=model_id,
        api_key_encrypted=encrypted_key,
        is_default=is_first,
        is_active=True,
    )

    db.add(provider)
    await db.commit()

    # Return updated providers list
    return await _render_providers_list(request, db, current_user.id)


@router.post("/settings/providers/{provider_id}/test", response_class=HTMLResponse)
async def test_provider(
    request: Request,
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test an AI provider connection."""
    from app.ai.factory import get_ai_provider
    from app.models.ai_provider import AIProvider as AIProviderModel

    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider_config = result.scalar_one_or_none()

    if not provider_config:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Provider not found",
            },
        )

    try:
        provider = await get_ai_provider(db, provider_id)
        success = await provider.health_check()

        if success:
            return templates.TemplateResponse(
                request=request,
                name="components/toast.html",
                context={
                    "toast_type": "success",
                    "toast_message": f"Successfully connected to {provider_config.display_name}",
                },
            )
        else:
            return templates.TemplateResponse(
                request=request,
                name="components/toast.html",
                context={
                    "toast_type": "error",
                    "toast_message": "Connection failed - please check your API key",
                },
            )
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": f"Error: {str(e)}",
            },
        )


@router.post("/settings/providers/{provider_id}/default", response_class=HTMLResponse)
async def set_default_provider(
    request: Request,
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a provider as default."""
    from app.models.ai_provider import AIProvider as AIProviderModel

    # Unset all defaults
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.user_id == current_user.id,
            AIProviderModel.is_default == True,  # noqa: E712
        )
    )
    for p in result.scalars().all():
        p.is_default = False

    # Set new default
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider:
        provider.is_default = True

    await db.commit()

    # Return updated providers list
    return await _render_providers_list(request, db, current_user.id)


@router.delete("/settings/providers/{provider_id}", response_class=HTMLResponse)
async def delete_provider(
    request: Request,
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an AI provider."""
    from app.models.ai_provider import AIProvider as AIProviderModel

    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()

    if provider:
        was_default = provider.is_default
        await db.delete(provider)
        await db.commit()

        # If deleted provider was default, make another one default
        if was_default:
            result = await db.execute(
                select(AIProviderModel).where(AIProviderModel.user_id == current_user.id).limit(1)
            )
            new_default = result.scalar_one_or_none()
            if new_default:
                new_default.is_default = True
                await db.commit()

    # Return empty string to remove the element
    return ""


async def _render_providers_list(request: Request, db: AsyncSession, user_id: UUID) -> HTMLResponse:
    """Helper to render the providers list partial."""
    from app.models.ai_provider import AIProvider as AIProviderModel
    from app.utils.encryption import decrypt_api_key, mask_api_key

    result = await db.execute(
        select(AIProviderModel)
        .where(AIProviderModel.user_id == user_id)
        .order_by(AIProviderModel.created_at)
    )
    provider_models = result.scalars().all()

    providers = []
    for p in provider_models:
        api_key = decrypt_api_key(p.api_key_encrypted)
        providers.append({
            "id": str(p.id),
            "provider_name": p.provider_name.value if hasattr(p.provider_name, 'value') else str(p.provider_name),
            "display_name": p.display_name,
            "model_id": p.model_id,
            "api_key_masked": mask_api_key(api_key),
            "is_default": p.is_default,
            "is_active": p.is_active,
        })

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_providers_list.html",
        context={"providers": providers},
    )


@router.patch("/settings/colors/{color_id}", response_class=HTMLResponse)
async def update_color(
    request: Request,
    color_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a color label name."""
    form = await request.form()
    name = form.get("name")

    result = await db.execute(
        select(Color).where(
            Color.id == color_id,
            Color.user_id == current_user.id,
        )
    )
    color = result.scalar_one_or_none()

    if color and name:
        color.name = name
        await db.commit()
        await db.refresh(color)

    # Fetch all colors and return the full section (includes OOB swap for sidebar)
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_colors.html",
        context={"colors": colors},
    )


@router.post("/settings/colors", response_class=HTMLResponse)
async def create_color(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new color label."""
    form = await request.form()
    name = form.get("name", "New Color")
    hex_value = form.get("hex_value", "#808080")

    # Get the max position for ordering
    result = await db.execute(
        select(func.max(Color.position))
        .where(Color.user_id == current_user.id)
    )
    max_position = result.scalar() or 0

    # Create new color
    color = Color(
        user_id=current_user.id,
        name=name,
        hex_value=hex_value,
        position=max_position + 1,
    )
    db.add(color)
    await db.commit()
    await db.refresh(color)

    # Fetch all colors and return the full section
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_colors.html",
        context={"colors": colors},
    )


@router.delete("/settings/colors/{color_id}", response_class=HTMLResponse)
async def delete_color(
    request: Request,
    color_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a color label. Articles with this color will have their color cleared."""
    # Find the color
    result = await db.execute(
        select(Color).where(
            Color.id == color_id,
            Color.user_id == current_user.id,
        )
    )
    color = result.scalar_one_or_none()

    if not color:
        return HTMLResponse("<div>Color not found</div>", status_code=404)

    # Clear color from articles that use it
    await db.execute(
        Article.__table__.update()
        .where(Article.color_id == color_id)
        .values(color_id=None)
    )

    # Delete the color
    await db.delete(color)
    await db.commit()

    # Fetch remaining colors and return the full section
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_colors.html",
        context={"colors": colors},
    )


# =============================================================================
# Modal Routes
# =============================================================================


@router.get("/modals/add-article", response_class=HTMLResponse)
async def add_article_modal(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the add article modal HTML."""
    return templates.TemplateResponse(
        request=request,
        name="modals/add_article.html",
        context={},
    )


# =============================================================================
# Article HTMX Routes
# =============================================================================


@router.post("/articles/add", response_class=HTMLResponse)
async def add_article_url(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an article from URL via HTMX."""
    from app.database import async_session_maker
    from app.extractors import extract_content
    from app.models.article import Article, ProcessingStatus, SourceType

    form = await request.form()
    url = form.get("url")

    if not url:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Please enter a URL",
            },
        )

    try:
        # Extract content from URL
        content = await extract_content(url=url)

        # Determine source type
        source_type = SourceType(content.source_type)

        # Create article
        article = Article(
            user_id=current_user.id,
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

        db.add(article)
        await db.commit()
        await db.refresh(article)

        # Schedule background processing
        async def process_in_background(article_id: UUID, user_id: UUID):
            async with async_session_maker() as bg_db:
                try:
                    from app.ai.service import AIService
                    ai_service = AIService(bg_db)
                    await ai_service.process_article(article_id=article_id, user_id=user_id)
                except Exception as e:
                    import logging
                    logging.error(f"Background processing failed: {e}")

        background_tasks.add_task(process_in_background, article.id, current_user.id)

        # Return success toast + trigger to close modal and refresh list
        response = templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "success",
                "toast_message": f"Added: {article.title[:50]}{'...' if len(article.title or '') > 50 else ''}",
            },
        )
        # Add HX-Trigger to close modal and refresh articles
        response.headers["HX-Trigger"] = "articleAdded"
        return response

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": f"Failed to add article: {str(e)[:100]}",
            },
        )


@router.post("/articles/upload", response_class=HTMLResponse)
async def upload_article_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF article via HTMX."""
    import tempfile
    from pathlib import Path

    from app.database import async_session_maker
    from app.extractors import extract_content
    from app.models.article import Article, ProcessingStatus, SourceType

    form = await request.form()
    file = form.get("file")

    if not file or not hasattr(file, "filename"):
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Please select a PDF file",
            },
        )

    if not file.filename.lower().endswith(".pdf"):
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Only PDF files are supported",
            },
        )

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Extract content from PDF
        extracted = await extract_content(file_path=temp_path)

        # Create article
        article = Article(
            user_id=current_user.id,
            source_type=SourceType.PDF,
            title=extracted.title or file.filename,
            authors=extracted.authors,
            extracted_text=extracted.text,
            word_count=len(extracted.text.split()) if extracted.text else None,
            file_path=f"uploads/{current_user.id}/{file.filename}",
            article_metadata=extracted.metadata,
            processing_status=ProcessingStatus.PENDING,
        )

        db.add(article)
        await db.commit()
        await db.refresh(article)

        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)

        # Schedule background processing
        async def process_in_background(article_id: UUID, user_id: UUID):
            async with async_session_maker() as bg_db:
                try:
                    from app.ai.service import AIService
                    ai_service = AIService(bg_db)
                    await ai_service.process_article(article_id=article_id, user_id=user_id)
                except Exception as e:
                    import logging
                    logging.error(f"Background processing failed: {e}")

        background_tasks.add_task(process_in_background, article.id, current_user.id)

        # Return success toast
        response = templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "success",
                "toast_message": f"Uploaded: {article.title[:50]}{'...' if len(article.title or '') > 50 else ''}",
            },
        )
        response.headers["HX-Trigger"] = "articleAdded"
        return response

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": f"Failed to upload PDF: {str(e)[:100]}",
            },
        )


# =============================================================================
# Bulk Article Operations
# =============================================================================


@router.post("/articles/bulk/mark-read", response_class=HTMLResponse)
async def bulk_mark_read(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark selected articles as read and optionally assign a color."""
    import json

    form = await request.form()
    article_ids_json = form.get("article_ids", "[]")
    color_id = form.get("color_id")

    try:
        article_ids = json.loads(article_ids_json)
    except json.JSONDecodeError:
        article_ids = []

    if not article_ids:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "No articles selected",
            },
        )

    # Update articles
    count = 0
    for article_id in article_ids:
        try:
            result = await db.execute(
                select(Article).where(
                    Article.id == article_id,
                    Article.user_id == current_user.id,
                )
            )
            article = result.scalar_one_or_none()
            if article:
                article.is_read = True
                if color_id:
                    article.color_id = color_id
                count += 1
        except Exception:
            continue

    await db.commit()

    # Return success toast and trigger refresh
    response = templates.TemplateResponse(
        request=request,
        name="components/toast.html",
        context={
            "toast_type": "success",
            "toast_message": f"Marked {count} article{'s' if count != 1 else ''} as read",
        },
    )
    response.headers["HX-Trigger"] = "articlesUpdated"
    return response


@router.post("/articles/bulk/mark-unread", response_class=HTMLResponse)
async def bulk_mark_unread(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark selected articles as unread."""
    import json

    form = await request.form()
    article_ids_json = form.get("article_ids", "[]")

    try:
        article_ids = json.loads(article_ids_json)
    except json.JSONDecodeError:
        article_ids = []

    if not article_ids:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "No articles selected",
            },
        )

    # Update articles
    count = 0
    for article_id in article_ids:
        try:
            result = await db.execute(
                select(Article).where(
                    Article.id == article_id,
                    Article.user_id == current_user.id,
                )
            )
            article = result.scalar_one_or_none()
            if article:
                article.is_read = False
                count += 1
        except Exception:
            continue

    await db.commit()

    # Return success toast and trigger refresh
    response = templates.TemplateResponse(
        request=request,
        name="components/toast.html",
        context={
            "toast_type": "success",
            "toast_message": f"Marked {count} article{'s' if count != 1 else ''} as unread",
        },
    )
    response.headers["HX-Trigger"] = "articlesUpdated"
    return response


@router.get("/sidebar/unread-count", response_class=HTMLResponse)
async def sidebar_unread_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the sidebar unread count partial for HTMX updates."""
    # Count unread articles
    result = await db.execute(
        select(func.count(Article.id)).where(
            Article.user_id == current_user.id,
            Article.is_read == False,
        )
    )
    unread_count = result.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_unread_count.html",
        context={
            "unread_count": unread_count,
            "current_path": str(request.url.path),
        },
    )


@router.get("/articles/bulk/color-picker", response_class=HTMLResponse)
async def bulk_color_picker(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the color picker dropdown for bulk mark as read."""
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/bulk_color_picker.html",
        context={"colors": colors},
    )


@router.post("/articles/bulk/delete", response_class=HTMLResponse)
async def bulk_delete(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete selected articles."""
    import json

    form = await request.form()
    article_ids_json = form.get("article_ids", "[]")

    try:
        article_ids = json.loads(article_ids_json)
    except json.JSONDecodeError:
        article_ids = []

    if not article_ids:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "No articles selected",
            },
        )

    # Delete articles
    count = 0
    for article_id in article_ids:
        try:
            result = await db.execute(
                select(Article).where(
                    Article.id == article_id,
                    Article.user_id == current_user.id,
                )
            )
            article = result.scalar_one_or_none()
            if article:
                await db.delete(article)
                count += 1
        except Exception:
            continue

    await db.commit()

    # Return success toast and trigger refresh
    response = templates.TemplateResponse(
        request=request,
        name="components/toast.html",
        context={
            "toast_type": "success",
            "toast_message": f"Deleted {count} article{'s' if count != 1 else ''}",
        },
    )
    response.headers["HX-Trigger"] = "articlesUpdated"
    return response


@router.post("/articles/bulk/color", response_class=HTMLResponse)
async def bulk_update_color(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update color for selected articles."""
    import json

    form = await request.form()
    article_ids_json = form.get("article_ids", "[]")
    color_id = form.get("color_id")

    try:
        article_ids = json.loads(article_ids_json)
    except json.JSONDecodeError:
        article_ids = []

    if not article_ids:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "No articles selected",
            },
        )

    # Update articles
    count = 0
    for article_id in article_ids:
        try:
            result = await db.execute(
                select(Article).where(
                    Article.id == article_id,
                    Article.user_id == current_user.id,
                )
            )
            article = result.scalar_one_or_none()
            if article:
                article.color_id = UUID(color_id) if color_id else None
                count += 1
        except Exception:
            continue

    await db.commit()

    # Return success toast and trigger refresh
    response = templates.TemplateResponse(
        request=request,
        name="components/toast.html",
        context={
            "toast_type": "success",
            "toast_message": f"Updated color for {count} article{'s' if count != 1 else ''}",
        },
    )
    response.headers["HX-Trigger"] = "articlesUpdated"
    return response


@router.post("/articles/bulk/reanalyze", response_class=HTMLResponse)
async def bulk_reanalyze(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-analyze selected articles (re-generate summary and categories)."""
    import json

    from app.database import async_session_maker

    form = await request.form()
    article_ids_json = form.get("article_ids", "[]")

    try:
        article_ids = json.loads(article_ids_json)
    except json.JSONDecodeError:
        article_ids = []

    if not article_ids:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "No articles selected",
            },
        )

    # Queue articles for reprocessing
    queued = 0
    skipped = 0
    for article_id in article_ids:
        try:
            result = await db.execute(
                select(Article).where(
                    Article.id == article_id,
                    Article.user_id == current_user.id,
                )
            )
            article = result.scalar_one_or_none()
            if article:
                # Skip if already processing
                if article.processing_status == ProcessingStatus.PROCESSING:
                    skipped += 1
                    continue

                # Mark as pending
                article.processing_status = ProcessingStatus.PENDING
                article.processing_error = None
                queued += 1
        except Exception:
            continue

    await db.commit()

    # Schedule background processing for all queued articles
    async def process_in_background(aid: UUID, uid: UUID):
        async with async_session_maker() as bg_db:
            try:
                from app.ai.service import AIService
                ai_service = AIService(bg_db)
                await ai_service.process_article(article_id=aid, user_id=uid)
            except Exception as e:
                import logging
                logging.error(f"Background reprocessing failed for {aid}: {e}")

    for article_id in article_ids:
        try:
            background_tasks.add_task(process_in_background, UUID(article_id), current_user.id)
        except Exception:
            continue

    # Build response message
    message_parts = []
    if queued > 0:
        message_parts.append(f"Re-analyzing {queued} article{'s' if queued != 1 else ''}")
    if skipped > 0:
        message_parts.append(f"Skipped {skipped} already processing")

    response = templates.TemplateResponse(
        request=request,
        name="components/toast.html",
        context={
            "toast_type": "success" if queued > 0 else "warning",
            "toast_message": ". ".join(message_parts) if message_parts else "No articles to process",
        },
    )
    response.headers["HX-Trigger"] = "articlesUpdated"
    return response


# =============================================================================
# Remote Add Route
# =============================================================================


@router.get("/remote", response_class=HTMLResponse)
async def remote_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remote add page - WhatsApp bot setup instructions."""
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="pages/remote.html",
        context={
            "current_path": "/app/remote",
            **sidebar_data,
        },
    )


# =============================================================================
# Ask / Chat Routes
# =============================================================================


@router.get("/ask", response_class=HTMLResponse)
async def ask_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat page for asking questions about your library."""
    # Fetch sidebar data
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    # Example questions to show in empty state
    example_questions = [
        "What are the main topics covered in my articles?",
        "Summarize what I've saved about machine learning",
        "What do my articles say about productivity?",
        "How many articles do I have in each category?",
    ]

    return templates.TemplateResponse(
        request=request,
        name="pages/ask.html",
        context={
            "current_path": "/app/ask",
            "example_questions": example_questions,
            **sidebar_data,
        },
    )


@router.post("/ask/query")
async def ask_query(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle a question about the user's library with streaming response."""
    import html
    import logging
    import re
    import uuid

    from sqlalchemy import func as sqla_func

    from app.ai.embeddings import generate_query_embedding
    from app.ai.factory import get_default_provider
    from app.ai.prompts import truncate_text
    from app.models.article import Article, ProcessingStatus

    logger = logging.getLogger(__name__)

    form = await request.form()
    question = form.get("question", "").strip()

    if not question:
        return HTMLResponse(
            templates.get_template("components/toast.html").render(
                toast_type="error",
                toast_message="Please enter a question",
            )
        )

    message_id = str(uuid.uuid4())[:8]

    # Render user's question
    user_message_html = templates.get_template("partials/chat_message_user.html").render(
        message=question
    )

    async def generate_response():
        """Generator that yields HTML chunks for streaming."""
        # First, send the user message
        yield user_message_html

        try:
            # Get AI provider
            provider = await get_default_provider(db, current_user.id)
            if not provider:
                yield templates.get_template("partials/chat_message_assistant.html").render(
                    message_id=message_id,
                    content="",
                    sources=[],
                    is_streaming=False,
                    error="No AI provider configured. Please add one in Settings.",
                )
                return

            # Show typing indicator while searching
            yield f'''<div class="flex justify-start mb-4" id="message-{message_id}">
                <div class="max-w-[80%]">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 rounded-full bg-article-blue/10 flex items-center justify-center flex-shrink-0">
                            <svg class="w-4 h-4 text-article-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>
                            </svg>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="bg-dark-surface border border-dark-border rounded-2xl rounded-tl-md px-4 py-3">
                                <div id="content-{message_id}" class="chat-prose text-dark-text text-sm">
                                    <div class="flex items-center gap-1">
                                        <div class="w-2 h-2 bg-article-blue rounded-full animate-pulse"></div>
                                        <div class="w-2 h-2 bg-article-blue rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
                                        <div class="w-2 h-2 bg-article-blue rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>'''

            # Perform hybrid search
            semantic_results = []
            keyword_results = []

            # Semantic Search
            has_embeddings = hasattr(Article, "embedding")
            if has_embeddings:
                try:
                    query_embedding = generate_query_embedding(question)
                    if query_embedding:
                        distance = Article.embedding.cosine_distance(query_embedding)
                        semantic_query = (
                            select(Article, distance.label("distance"))
                            .where(Article.user_id == current_user.id)
                            .where(Article.processing_status == ProcessingStatus.COMPLETED)
                            .where(Article.embedding.isnot(None))
                            .order_by(distance)
                            .limit(10)
                        )
                        result = await db.execute(semantic_query)
                        semantic_results = [(row[0], row[1]) for row in result.all()]
                except Exception as e:
                    logger.warning(f"Semantic search failed: {e}")

            # Keyword Search
            try:
                search_words = question.lower().split()[:10]
                valid_words = [w for w in search_words if len(w) >= 3]
                conditions = []

                for word in valid_words[:5]:
                    conditions.append(Article.title.ilike(f"%{word}%"))

                ts_query = sqla_func.plainto_tsquery("english", question)
                conditions.append(Article.search_vector.op("@@")(ts_query))

                if conditions:
                    ts_rank = sqla_func.ts_rank(Article.search_vector, ts_query)
                    keyword_query = (
                        select(Article, ts_rank.label("rank"))
                        .where(Article.user_id == current_user.id)
                        .where(Article.processing_status == ProcessingStatus.COMPLETED)
                        .where(or_(*conditions))
                        .order_by(ts_rank.desc())
                        .limit(10)
                    )
                    result = await db.execute(keyword_query)
                    keyword_results = [(row[0], row[1]) for row in result.all()]
            except Exception as e:
                logger.warning(f"Keyword search failed: {e}")

            # Merge Results
            article_scores = {}
            for article, distance in semantic_results:
                article_id = str(article.id)
                semantic_score = max(0, 1 - distance)
                article_scores[article_id] = article_scores.get(article_id, 0) + semantic_score

            max_rank = max((r for _, r in keyword_results), default=1) or 1
            for article, rank in keyword_results:
                article_id = str(article.id)
                keyword_score = rank / max_rank if max_rank > 0 else 0
                article_scores[article_id] = article_scores.get(article_id, 0) + keyword_score

            all_articles = {str(a.id): a for a, _ in semantic_results + keyword_results}
            sorted_ids = sorted(article_scores.keys(), key=lambda x: article_scores[x], reverse=True)

            merged_articles = []
            seen_ids = set()
            for article_id in sorted_ids[:10]:
                if article_id not in seen_ids:
                    seen_ids.add(article_id)
                    merged_articles.append(all_articles[article_id])

            # Fallback if no results
            if not merged_articles:
                query = (
                    select(Article)
                    .where(Article.user_id == current_user.id)
                    .where(Article.processing_status == ProcessingStatus.COMPLETED)
                    .order_by(Article.created_at.desc())
                    .limit(5)
                )
                result = await db.execute(query)
                merged_articles = list(result.scalars().all())

            if not merged_articles:
                # Replace typing indicator with error message
                yield f'''<script>document.getElementById('message-{message_id}').outerHTML = `
                    {templates.get_template("partials/chat_message_assistant.html").render(
                        message_id=message_id,
                        content="You don't have any processed articles yet. Add some articles and wait for them to be processed.",
                        sources=[],
                        is_streaming=False,
                        error=None,
                    ).replace('`', '\\`').replace('${', '\\${')}`;</script>'''
                return

            # Build context
            context_parts = []
            sources = []
            for article in merged_articles:
                article_context = f"### {article.title}\n\n"
                if article.summary:
                    article_context += f"**Summary:**\n{article.summary}\n\n"
                if article.extracted_text:
                    excerpt = truncate_text(article.extracted_text, 2000)
                    article_context += f"**Content excerpt:**\n{excerpt}\n"
                context_parts.append(article_context)
                sources.append({"id": str(article.id), "title": article.title})

            context = "\n\n---\n\n".join(context_parts)

            # Stream AI response
            full_response = ""
            async for chunk in provider.answer_question_stream(question=question, context=context):
                full_response += chunk
                # Escape the chunk for safe HTML/JS insertion
                escaped_chunk = html.escape(chunk).replace('\n', '\\n').replace('\r', '\\r')
                # Update the content div with the accumulated response
                yield f'''<script>
                    (function() {{
                        var el = document.getElementById('content-{message_id}');
                        if (el) {{
                            var current = el.getAttribute('data-raw') || '';
                            current += "{escaped_chunk}";
                            el.setAttribute('data-raw', current);
                            el.innerHTML = current.replace(/\\n/g, '<br>');
                        }}
                    }})();
                </script>'''

            # Convert final markdown to HTML
            html_answer = full_response
            html_answer = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_answer)
            html_answer = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_answer)
            html_answer = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', html_answer, flags=re.DOTALL)
            html_answer = re.sub(r'`(.+?)`', r'<code>\1</code>', html_answer)
            html_answer = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r'^- (.+)$', r'<li>\1</li>', html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html_answer)
            html_answer = re.sub(r'\n\n', '</p><p>', html_answer)
            html_answer = f'<p>{html_answer}</p>'
            html_answer = re.sub(r'<p>\s*</p>', '', html_answer)

            # Replace entire message with final formatted version including sources
            final_html = templates.get_template("partials/chat_message_assistant.html").render(
                message_id=message_id,
                content=html_answer,
                sources=sources[:5],
                is_streaming=False,
                error=None,
            )
            # Escape for JS string
            final_html_escaped = final_html.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
            yield f'''<script>document.getElementById('message-{message_id}').outerHTML = `{final_html_escaped}`;</script>'''

        except Exception as e:
            logger.error(f"Ask query failed: {e}")
            error_html = templates.get_template("partials/chat_message_assistant.html").render(
                message_id=message_id,
                content="",
                sources=[],
                is_streaming=False,
                error=f"Sorry, something went wrong: {str(e)[:100]}",
            )
            error_html_escaped = error_html.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
            yield f'''<script>document.getElementById('message-{message_id}').outerHTML = `{error_html_escaped}`;</script>'''

    return StreamingResponse(
        generate_response(),
        media_type="text/html",
    )


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


# =============================================================================
# Reader Routes - Read through unread articles one by one
# =============================================================================


async def get_unread_articles_ordered(db: AsyncSession, user_id: UUID) -> list[Article]:
    """Get all unread articles (is_read == False), ordered by created_at."""
    result = await db.execute(
        select(Article)
        .where(Article.user_id == user_id, Article.is_read == False)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.color),
        )
        .order_by(Article.created_at.asc())
    )
    return list(result.scalars().all())


@router.get("/reader", response_class=HTMLResponse)
async def reader_index(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reader page - redirects to first unread article or shows 'all caught up'."""
    from fastapi.responses import RedirectResponse

    unread = await get_unread_articles_ordered(db, current_user.id)

    if not unread:
        # Show "all caught up" page
        return templates.TemplateResponse(
            request=request,
            name="pages/reader_empty.html",
            context={"current_path": "/app/reader"},
        )

    # Redirect to first unread article
    return RedirectResponse(url=f"/app/reader/{unread[0].id}", status_code=302)


@router.get("/reader/{article_id}", response_class=HTMLResponse)
async def reader_article(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Show a specific article in reader mode."""
    # Fetch the article
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.color),
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        return templates.TemplateResponse(
            request=request,
            name="pages/not_found.html",
            context={"message": "Article not found"},
            status_code=404,
        )

    # Get all unread articles for navigation
    unread = await get_unread_articles_ordered(db, current_user.id)
    unread_ids = [str(a.id) for a in unread]

    # Find current position
    current_id = str(article_id)
    if current_id in unread_ids:
        current_position = unread_ids.index(current_id) + 1
    else:
        # Article is already read, but we're viewing it anyway
        current_position = 0

    total_unread = len(unread_ids)

    # Get prev/next IDs
    prev_id = None
    next_id = None
    if current_id in unread_ids:
        idx = unread_ids.index(current_id)
        if idx > 0:
            prev_id = unread_ids[idx - 1]
        if idx < len(unread_ids) - 1:
            next_id = unread_ids[idx + 1]

    # Fetch colors for mark-as-read modal
    colors = await fetch_colors(db, current_user.id)

    # Convert article to dict
    article_dict = article_to_detail_dict(article)

    # Extract domain from URL
    source_domain = None
    if article.original_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(article.original_url)
            source_domain = parsed.netloc.replace("www.", "")
        except Exception:
            pass

    return templates.TemplateResponse(
        request=request,
        name="pages/reader.html",
        context={
            "article": article_dict,
            "source_domain": source_domain,
            "current_position": current_position,
            "total_unread": total_unread,
            "prev_id": prev_id,
            "next_id": next_id,
            "colors": colors,
            "current_path": "/app/reader",
        },
    )


@router.post("/reader/{article_id}/mark-read", response_class=HTMLResponse)
async def reader_mark_read(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark article as read and redirect to next unread article."""
    from fastapi.responses import RedirectResponse

    # Update the article
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if article:
        article.is_read = True
        await db.commit()

    # Get next unread article
    unread = await get_unread_articles_ordered(db, current_user.id)

    if unread:
        # Redirect to next unread
        return RedirectResponse(url=f"/app/reader/{unread[0].id}", status_code=302)
    else:
        # All done - redirect to empty state
        return RedirectResponse(url="/app/reader", status_code=302)


@router.post("/reader/{article_id}/set-color", response_class=HTMLResponse)
async def reader_set_color(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set or clear the color label on an article and reload the reader page."""
    from fastapi.responses import RedirectResponse

    form = await request.form()
    color_id = form.get("color_id")

    # Update the article
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if article:
        article.color_id = UUID(color_id) if color_id else None
        await db.commit()

    # Redirect back to the same article
    return RedirectResponse(url=f"/app/reader/{article_id}", status_code=302)
