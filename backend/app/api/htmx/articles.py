from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.article import Article, ProcessingStatus
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.category import Category
from app.models.color import Color
from app.models.note import Note
from app.models.user import User
from app.services.article_service import ArticleService, process_article_background_task
from app.utils.auth import get_current_user

from .utils import (
    article_to_detail_dict,
    article_to_dict,
    fetch_categories_with_counts,
    fetch_colors,
    fetch_sidebar_data,
    fetch_tags,
    templates,
)

router = APIRouter()

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
    service = ArticleService(db)
    # Fetch all articles (no pagination)
    articles, total = await service.list_articles(
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


@router.get("/article/{article_id}/card", response_class=HTMLResponse)
async def get_article_card(
    request: Request,
    article_id: UUID,
    view_mode: str = Query("grid", description="View mode: grid or list"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single article card - used for polling during processing."""
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

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


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail_page(
    request: Request,
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Article detail page."""
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

    if not article:
        return templates.TemplateResponse(
            request=request,
            name="pages/not_found.html",
            context={"message": "Article not found"},
            status_code=404,
        )

    # Convert article to template-friendly dict
    article_dict = article_to_detail_dict(article)

    # Notes are already loaded by service.get_article and handled in article_to_detail_dict

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
):
    """Delete a single article via HTMX."""
    service = ArticleService(db)

    # Get article first to get title for toast
    article = await service.get_article(article_id, current_user.id)
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
    await service.delete_article(article_id, current_user.id)

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
):
    """Toggle article read/unread status via HTMX."""
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

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
    await service.update_article(article_id, current_user.id, is_read=not article.is_read)

    # Return updated button section
    return templates.TemplateResponse(
        request=request,
        name="partials/article_read_status_section.html",
        context={
            "article": {
                "id": str(article.id),
                "is_read": not article.is_read, # We just toggled it
            },
        },
    )


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

    service = ArticleService(db)
    article = await service.update_article(article_id, current_user.id, color_id=color_id)

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

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
):
    """Update article categories via HTMX."""
    form = await request.form()
    # Get all category_ids from form (checkboxes send multiple values)
    category_ids_str = form.getlist("category_ids")
    category_ids = [UUID(cid) for cid in category_ids_str]

    service = ArticleService(db)
    article = await service.update_article(article_id, current_user.id, category_ids=category_ids)

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

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
    form = await request.form()
    tag_ids_str = form.getlist("tag_ids")
    tag_ids = [UUID(tid) for tid in tag_ids_str]

    service = ArticleService(db)
    article = await service.update_article(article_id, current_user.id, tag_ids=tag_ids)

    if not article:
        return HTMLResponse("<div>Article not found</div>", status_code=404)

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
):
    """Create a note for an article via HTMX."""
    form = await request.form()
    content = form.get("content", "").strip()

    if not content:
        return HTMLResponse("<div>Note content is required</div>", status_code=400)

    # Verify article belongs to user
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

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
):
    """Reprocess an article (regenerate summary and categories) via HTMX."""
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

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
    background_tasks.add_task(process_article_background_task, article_id, current_user.id)

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
):
    """Get article processing status - used for polling during reprocessing."""
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

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
    return HTMLResponse(f"""
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
    """)


@router.delete("/article/{article_id}/notes/{note_id}", response_class=HTMLResponse)
async def delete_article_note(
    request: Request,
    article_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note via HTMX."""
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


@router.post("/articles/add", response_class=HTMLResponse)
async def add_article_url(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an article from URL via HTMX."""
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
        service = ArticleService(db)
        article = await service.create_article_from_url(
            url=url,
            user_id=current_user.id,
            background_tasks=background_tasks
        )

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

        service = ArticleService(db)
        article = await service.create_article_from_upload(
            file_path=temp_path,
            filename=file.filename,
            user_id=current_user.id,
            background_tasks=background_tasks
        )

        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)

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

# Bulk Operations
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
    service = ArticleService(db)
    for article_id_str in article_ids:
        try:
            article_id = UUID(article_id_str)
            # Just simple update loop for now
            await service.update_article(article_id, current_user.id, is_read=True, color_id=UUID(color_id) if color_id else None)
            count += 1
        except Exception:
            continue

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
    service = ArticleService(db)
    for article_id_str in article_ids:
        try:
            article_id = UUID(article_id_str)
            await service.update_article(article_id, current_user.id, is_read=False)
            count += 1
        except Exception:
            continue

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
    service = ArticleService(db)
    for article_id_str in article_ids:
        try:
            article_id = UUID(article_id_str)
            if await service.delete_article(article_id, current_user.id):
                count += 1
        except Exception:
            continue

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
    service = ArticleService(db)
    for article_id_str in article_ids:
        try:
            article_id = UUID(article_id_str)
            await service.update_article(article_id, current_user.id, color_id=UUID(color_id) if color_id else None)
            count += 1
        except Exception:
            continue

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
    service = ArticleService(db)

    for article_id_str in article_ids:
        try:
            article_id = UUID(article_id_str)
            article = await service.get_article(article_id, current_user.id)
            if article:
                # Skip if already processing
                if article.processing_status == ProcessingStatus.PROCESSING:
                    skipped += 1
                    continue

                # Mark as pending
                article.processing_status = ProcessingStatus.PENDING
                article.processing_error = None
                queued += 1

                # Schedule background processing
                background_tasks.add_task(process_article_background_task, article.id, current_user.id)
        except Exception:
            continue

    await db.commit()

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

# Taxonomy Optimization Routes

@router.get("/taxonomy/optimize", response_class=HTMLResponse)
async def taxonomy_optimize_modal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Show the taxonomy optimization modal with loading state."""
    # Count articles
    result = await db.execute(
        select(func.count(Article.id)).where(Article.user_id == current_user.id)
    )
    article_count = result.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="partials/taxonomy_optimize_modal.html",
        context={
            "article_count": article_count,
            "loading": True,
        },
    )


@router.post("/taxonomy/analyze", response_class=HTMLResponse)
async def taxonomy_analyze(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run AI analysis and return the preview of proposed changes."""
    from app.ai.factory import get_default_provider
    from app.ai.llm import LiteLLMProvider
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get AI provider
        provider = await get_default_provider(db, current_user.id)
        if not provider:
            return templates.TemplateResponse(
                request=request,
                name="partials/taxonomy_optimize_modal.html",
                context={
                    "error": "No AI provider configured. Please add one in Settings.",
                },
            )

        # Fetch all articles with their current categories
        result = await db.execute(
            select(Article)
            .where(Article.user_id == current_user.id)
            .options(selectinload(Article.categories).selectinload(ArticleCategory.category))
            .order_by(Article.created_at.desc())
        )
        articles = result.scalars().all()

        if not articles:
            return templates.TemplateResponse(
                request=request,
                name="partials/taxonomy_optimize_modal.html",
                context={
                    "error": "No articles in library to analyze.",
                },
            )

        # Prepare articles for AI analysis
        articles_for_ai = []
        for article in articles:
            current_cat = "Uncategorized"
            current_subcat = None

            # Get current category assignment
            if article.categories:
                for ac in article.categories:
                    if ac.category:
                        if ac.category.parent_id:
                            # This is a subcategory
                            current_subcat = ac.category.name
                            # Get parent
                            parent_result = await db.execute(
                                select(Category).where(Category.id == ac.category.parent_id)
                            )
                            parent = parent_result.scalar_one_or_none()
                            if parent:
                                current_cat = parent.name
                        else:
                            current_cat = ac.category.name

            articles_for_ai.append(
                {
                    "id": str(article.id),
                    "title": article.title or "Untitled",
                    "summary": article.summary or "",
                    "current_category": current_cat,
                    "current_subcategory": current_subcat,
                }
            )

        # Get current taxonomy structure
        async def get_category_tree(parent_id=None):
            result = await db.execute(
                select(Category)
                .where(
                    Category.user_id == current_user.id,
                    Category.parent_id == parent_id,
                )
                .order_by(Category.position)
            )
            cats = result.scalars().all()
            tree = []
            for cat in cats:
                children = await get_category_tree(cat.id)
                tree.append(
                    {
                        "name": cat.name,
                        "id": str(cat.id),
                        "children": children,
                    }
                )
            return tree

        current_taxonomy = await get_category_tree()

        # Call AI for taxonomy optimization
        if not isinstance(provider, LiteLLMProvider):
            return templates.TemplateResponse(
                request=request,
                name="partials/taxonomy_optimize_modal.html",
                context={
                    "error": "Provider does not support taxonomy optimization.",
                },
            )

        optimization_result = await provider.optimize_taxonomy(
            articles=articles_for_ai,
            current_taxonomy=current_taxonomy,
        )

        # Build article lookup for display
        article_lookup = {str(a.id): a for a in articles}

        # Convert taxonomy to JSON-serializable format for the hidden input
        import json

        taxonomy_for_json = [
            {
                "category": cat.category,
                "subcategories": [
                    {
                        "name": sub.name,
                        "article_ids": sub.article_ids,
                        "description": sub.description,
                    }
                    for sub in cat.subcategories
                ],
            }
            for cat in optimization_result.taxonomy
        ]
        taxonomy_json = json.dumps(taxonomy_for_json)

        return templates.TemplateResponse(
            request=request,
            name="partials/taxonomy_optimize_modal.html",
            context={
                "result": optimization_result,
                "taxonomy_json": taxonomy_json,
                "article_lookup": article_lookup,
                "article_count": len(articles),
                "loading": False,
            },
        )

    except Exception as e:
        logger.error(f"Taxonomy optimization failed: {e}")
        return templates.TemplateResponse(
            request=request,
            name="partials/taxonomy_optimize_modal.html",
            context={
                "error": f"Analysis failed: {str(e)}",
            },
        )


@router.post("/taxonomy/apply", response_class=HTMLResponse)
async def taxonomy_apply(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply the proposed taxonomy changes."""
    import json
    import logging
    logger = logging.getLogger(__name__)

    form = await request.form()
    taxonomy_json = form.get("taxonomy", "[]")

    try:
        taxonomy_data = json.loads(taxonomy_json)
    except json.JSONDecodeError:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Invalid taxonomy data",
            },
        )

    try:
        # Step 1: Delete ALL existing article-category associations for this user's articles
        user_article_ids = await db.execute(
            select(Article.id).where(Article.user_id == current_user.id)
        )
        article_id_list = [row[0] for row in user_article_ids.all()]

        if article_id_list:
            await db.execute(
                delete(ArticleCategory).where(ArticleCategory.article_id.in_(article_id_list))
            )

        # Step 2: Delete ALL existing categories for this user (children first, then parents)
        # First delete subcategories (those with parent_id)
        await db.execute(
            delete(Category).where(
                Category.user_id == current_user.id,
                Category.parent_id != None,
            )
        )
        # Then delete parent categories
        await db.execute(
            delete(Category).where(
                Category.user_id == current_user.id,
            )
        )
        await db.flush()

        # Step 3: Create the new taxonomy structure
        articles_updated = 0
        categories_created = 0
        subcategories_created = 0

        for cat_data in taxonomy_data:
            category_name = cat_data.get("category", "")

            # Find or create the top-level category
            cat_result = await db.execute(
                select(Category).where(
                    Category.user_id == current_user.id,
                    Category.name == category_name,
                    Category.parent_id == None,
                )
            )
            category = cat_result.scalar_one_or_none()

            if not category:
                category = Category(
                    user_id=current_user.id,
                    name=category_name,
                    parent_id=None,
                )
                db.add(category)
                await db.flush()
                categories_created += 1

            # Process subcategories
            for sub_data in cat_data.get("subcategories", []):
                subcat_name = sub_data.get("name", "")
                article_ids = sub_data.get("article_ids", [])

                # Find or create subcategory
                subcat_result = await db.execute(
                    select(Category).where(
                        Category.user_id == current_user.id,
                        Category.name == subcat_name,
                        Category.parent_id == category.id,
                    )
                )
                subcategory = subcat_result.scalar_one_or_none()

                if not subcategory:
                    subcategory = Category(
                        user_id=current_user.id,
                        name=subcat_name,
                        parent_id=category.id,
                    )
                    db.add(subcategory)
                    await db.flush()
                    subcategories_created += 1

                # Assign articles to this subcategory
                for article_id in article_ids:
                    try:
                        aid = UUID(article_id)

                        # Create new assignment (old ones already deleted above)
                        ac = ArticleCategory(
                            article_id=aid,
                            category_id=subcategory.id,
                            is_primary=True,
                            suggested_by_ai=True,
                        )
                        db.add(ac)
                        articles_updated += 1
                    except (ValueError, Exception) as e:
                        logger.warning(f"Failed to assign article {article_id}: {e}")
                        continue

        await db.commit()

        # Build success message
        message_parts = []
        if categories_created > 0:
            message_parts.append(f"{categories_created} new categories")
        if subcategories_created > 0:
            message_parts.append(f"{subcategories_created} new subcategories")
        message_parts.append(f"{articles_updated} articles reorganized")

        response = templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "success",
                "toast_message": "Taxonomy updated: " + ", ".join(message_parts),
            },
        )
        response.headers["HX-Trigger"] = "taxonomyApplied, sidebarRefresh"
        return response

    except Exception as e:
        logger.error(f"Failed to apply taxonomy: {e}")
        await db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": f"Failed to apply changes: {str(e)}",
            },
        )
