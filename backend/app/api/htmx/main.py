"""
Core HTMX routes for article operations.

Contains:
- Index page and article list views
- Article detail, card, and status endpoints
- Article CRUD (delete, toggle-read, update color/categories/tags)
- Article notes management
- Article reprocessing
- Remote add page and test routes
"""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Import helpers from the htmx helpers module
from app.api.htmx.helpers import (
    article_to_detail_dict,
    article_to_dict,
    fetch_categories_with_counts,
    fetch_colors,
    fetch_sidebar_data,
    fetch_tags,
)
from app.database import get_db
from app.models.article import Article, ProcessingStatus
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.category import Category
from app.models.color import Color
from app.models.tag import Tag
from app.models.user import User
from app.tasks import process_article_background
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Main Application Routes
# =============================================================================


@router.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    search: str | None = None,
    view: str = "grid",
    page: int = Query(1, ge=1),
    page_size: int = Query(1000, ge=1, le=10000),  # Show all articles by default
    category_id: UUID | None = None,
    color_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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
) -> Response:
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

    # Track if we need relevance ranking
    ts_query = None

    # Apply filters
    if search:
        # Create full-text search query for ranking
        ts_query = func.plainto_tsquery("english", search)

        # Subquery to find articles with matching tags (avoids JOIN issues with NULLs)
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

    # Add distinct to prevent duplicates from JOINs (category/tag filtering)
    if category_id or tag_id:
        query = query.distinct()

    # Get total count (after distinct to get accurate count)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply ordering - use relevance ranking when searching, otherwise by date
    if search and ts_query is not None:
        # Order by relevance (ts_rank), then by date as tiebreaker
        rank = func.ts_rank(Article.search_vector, ts_query)
        query = query.order_by(rank.desc(), Article.created_at.desc())
    else:
        query = query.order_by(Article.created_at.desc())

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    articles = result.scalars().all()

    return list(articles), total


# =============================================================================
# Article Card Route (for polling during processing)
# =============================================================================


@router.get("/article/{article_id}/card", response_class=HTMLResponse)
async def get_article_card(
    request: Request,
    article_id: UUID,
    view_mode: str = Query("grid", description="View mode: grid or list"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Get a single article card - used for polling during processing."""
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
        return HTMLResponse("")

    article_dict = article_to_dict(article)

    return templates.TemplateResponse(
        request=request,
        name="partials/article_card.html",
        context={
            "article": article_dict,
            "view_mode": view_mode,
        },
    )


# =============================================================================
# Test Routes (for development)
# =============================================================================


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail_page(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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
    notes_query = select(Note).where(Note.article_id == article_id).order_by(Note.created_at.desc())
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


@router.delete("/article/{article_id}", response_class=HTMLResponse)
async def delete_article(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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


@router.post("/article/{article_id}/toggle-read", response_class=HTMLResponse)
async def toggle_article_read(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Toggle article read/unread status via HTMX."""
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

    # Toggle the read status
    article.is_read = not article.is_read
    await db.commit()

    # Return updated button section
    return templates.TemplateResponse(
        request=request,
        name="partials/article_read_status_section.html",
        context={
            "article": {
                "id": str(article.id),
                "is_read": article.is_read,
            },
        },
    )


# =============================================================================
# Article Edit Routes (HTMX)
# =============================================================================


@router.patch("/article/{article_id}/color", response_class=HTMLResponse)
async def update_article_color(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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
        color_result = await db.execute(select(Color).where(Color.id == color_id))
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
) -> Response:
    """Update article categories via HTMX."""
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
    await db.execute(delete(ArticleCategory).where(ArticleCategory.article_id == article_id))

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
) -> Response:
    """Update article tags via HTMX."""
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
    await db.execute(delete(ArticleTag).where(ArticleTag.article_id == article_id))

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
        {"id": str(at.tag.id), "name": at.tag.name, "color": at.tag.color} for at in article.tags
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
) -> Response:
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
    await db.flush()  # Flush to get the ID and timestamp
    await db.refresh(note)  # Refresh to get DB-generated values
    await db.commit()

    # Fetch existing notes (excluding the new one to avoid duplicates)
    notes_result = await db.execute(
        select(Note)
        .where(Note.article_id == article_id, Note.id != note.id)
        .order_by(Note.created_at.desc())
    )
    existing_notes = notes_result.scalars().all()

    # Build list with new note first (it's newest)
    notes_list = [{"id": str(note.id), "content": note.content, "created_at": note.created_at}] + [
        {"id": str(n.id), "content": n.content, "created_at": n.created_at} for n in existing_notes
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
) -> Response:
    """Reprocess an article (regenerate summary and categories) via HTMX."""
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

    # Schedule background processing using module-level function
    background_tasks.add_task(process_article_background, article_id, current_user.id)

    # Return toast + OOB swap for processing banner
    toast_html = templates.get_template("components/toast.html").render(
        {
            "toast_type": "success",
            "toast_message": f"Re-analyzing: {article.title[:40]}{'...' if len(article.title or '') > 40 else ''}",
        }
    )

    # Build processing banner HTML with polling to check status
    processing_banner = f"""
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
    """

    return HTMLResponse(content=toast_html + processing_banner)


@router.get("/article/{article_id}/status", response_class=HTMLResponse)
async def get_article_processing_status(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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

    status = (
        article.processing_status.value
        if hasattr(article.processing_status, "value")
        else str(article.processing_status)
    )

    # If still processing, return banner with polling
    if status == "processing":
        return HTMLResponse(f"""
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
        """)

    # If failed, show error
    if status == "failed":
        error_msg = article.processing_error or "Unknown error"
        return HTMLResponse(f"""
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
        """)

    # Completed - show success briefly then trigger page refresh
    return HTMLResponse("""
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
    <script>setTimeout(function() { window.location.reload(); }, 1000);</script>
    """)


@router.delete("/article/{article_id}/notes/{note_id}", response_class=HTMLResponse)
async def delete_article_note(
    request: Request,
    article_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a note via HTMX."""
    from app.models.note import Note

    # Verify note belongs to user's article
    result = await db.execute(
        select(Note).join(Article).where(Note.id == note_id, Article.user_id == current_user.id)
    )
    note = result.scalar_one_or_none()

    if not note:
        return HTMLResponse("<div>Note not found</div>", status_code=404)

    await db.delete(note)
    await db.commit()

    # Expire all to clear cache, then fetch fresh notes
    db.expire_all()

    # Fetch remaining notes
    notes_result = await db.execute(
        select(Note).where(Note.article_id == article_id).order_by(Note.created_at.desc())
    )
    notes = notes_result.scalars().all()

    notes_list = [
        {"id": str(n.id), "content": n.content, "created_at": n.created_at} for n in notes
    ]

    return templates.TemplateResponse(
        request=request,
        name="partials/article_notes_section.html",
        context={
            "article": {"id": str(article_id), "notes": notes_list},
        },
    )


# =============================================================================
# Remote Add Route
# =============================================================================


@router.get("/remote", response_class=HTMLResponse)
async def remote_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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
# Test Routes (for development)
# =============================================================================


@router.get("/test", response_class=HTMLResponse)
async def test_page(request: Request) -> Response:
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
async def test_click(request: Request) -> Response:
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


# =============================================================================
# DEVELOPMENT-ONLY: Test Routes (used for previewing UI components)
# These routes are safe to keep - they use mock data and don't affect production
# =============================================================================

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
async def test_card(request: Request, view: str = "grid") -> Response:
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
