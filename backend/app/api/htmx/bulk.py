"""HTMX routes for bulk article operations."""

import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.htmx.helpers import fetch_colors
from app.database import get_db
from app.models.article import Article, ProcessingStatus
from app.models.user import User
from app.tasks import process_article_background
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Bulk Article Operations
# =============================================================================


@router.post("/articles/bulk/mark-read", response_class=HTMLResponse)
async def bulk_mark_read(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Mark selected articles as read and optionally assign a color."""
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
        except Exception as e:
            logger.warning(f"Failed to mark article {article_id} as read: {e}")
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
) -> Response:
    """Mark selected articles as unread."""
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
        except Exception as e:
            logger.warning(f"Failed to mark article {article_id} as unread: {e}")
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
) -> Response:
    """Return the sidebar unread count partial for HTMX updates."""
    # Count unread articles
    result = await db.execute(
        select(func.count(Article.id)).where(
            Article.user_id == current_user.id,
            Article.is_read.is_(False),
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
) -> Response:
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
) -> Response:
    """Delete selected articles."""
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
        except Exception as e:
            logger.warning(f"Failed to delete article {article_id}: {e}")
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
) -> Response:
    """Update color for selected articles."""
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
        except Exception as e:
            logger.warning(f"Failed to update color for article {article_id}: {e}")
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
) -> Response:
    """Re-analyze selected articles (re-generate summary and categories)."""
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
        except Exception as e:
            logger.warning(f"Failed to queue article {article_id} for reanalysis: {e}")
            continue

    await db.commit()

    # Schedule background processing for all queued articles using module-level function
    for article_id in article_ids:
        try:
            background_tasks.add_task(process_article_background, UUID(article_id), current_user.id)
        except Exception as e:
            logger.warning(f"Failed to schedule background task for article {article_id}: {e}")
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
            "toast_message": ". ".join(message_parts)
            if message_parts
            else "No articles to process",
        },
    )
    response.headers["HX-Trigger"] = "articlesUpdated"
    return response
