"""HTMX routes for reader mode - reading through unread articles one by one."""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.htmx.helpers import article_to_detail_dict, fetch_colors
from app.database import get_db
from app.models.article import Article
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.user import User
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Helper Functions
# =============================================================================


async def get_unread_articles_ordered(db: AsyncSession, user_id: UUID) -> list[Article]:
    """Get all unread articles (is_read == False), ordered by created_at."""
    result = await db.execute(
        select(Article)
        .where(Article.user_id == user_id, Article.is_read.is_(False))
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.color),
        )
        .order_by(Article.created_at.asc())
    )
    return list(result.scalars().all())


# =============================================================================
# Reader Routes
# =============================================================================


@router.get("/reader", response_class=HTMLResponse)
async def reader_index(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Reader page - redirects to first unread article or shows 'all caught up'."""
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
) -> Response:
    """Show a specific article in reader mode."""

    # Fetch the article with notes
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.color),
            selectinload(Article.notes),
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
        except Exception as e:
            logger.debug(f"Failed to extract domain from URL {article.original_url}: {e}")

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
) -> Response:
    """Mark article as read and redirect to next unread article."""
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
) -> Response:
    """Set or clear the color label on an article and reload the reader page."""
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
