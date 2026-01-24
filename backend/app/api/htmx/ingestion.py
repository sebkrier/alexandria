"""HTMX routes for article ingestion (URL and PDF upload)."""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.extractors import extract_content
from app.models.article import Article, ProcessingStatus, SourceType
from app.models.user import User
from app.tasks import process_article_background
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Modal Routes
# =============================================================================


@router.get("/modals/add-article", response_class=HTMLResponse)
async def add_article_modal(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Return the add article modal HTML."""
    return templates.TemplateResponse(
        request=request,
        name="modals/add_article.html",
        context={},
    )


# =============================================================================
# Article Ingestion Routes
# =============================================================================


@router.post("/articles/add", response_class=HTMLResponse)
async def add_article_url(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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

        # Schedule background processing using module-level function
        background_tasks.add_task(process_article_background, article.id, current_user.id)

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
) -> Response:
    """Upload a PDF article via HTMX."""
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

        # Schedule background processing using module-level function
        background_tasks.add_task(process_article_background, article.id, current_user.id)

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
