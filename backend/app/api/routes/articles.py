import logging
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query

logger = logging.getLogger(__name__)
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.article import Article, SourceType, ProcessingStatus
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.note import Note
from app.schemas.article import (
    ArticleCreateURL,
    ArticleResponse,
    ArticleListResponse,
    ArticleUpdate,
    CategoryBrief,
    TagBrief,
    AskRequest,
    AskResponse,
    ArticleReference,
)
from app.utils.auth import get_current_user
from app.extractors import extract_content
from app.ai.service import AIService
from app.ai.factory import get_default_provider
from app.ai.prompts import truncate_text

router = APIRouter()


def calculate_reading_time(word_count: int | None) -> int | None:
    """Calculate reading time in minutes (200 words per minute)"""
    if word_count is None:
        return None
    return max(1, round(word_count / 200))


def article_to_response(article: Article) -> ArticleResponse:
    """Convert Article model to response schema"""
    categories = []
    for ac in article.categories:
        categories.append(CategoryBrief(
            id=ac.category.id,
            name=ac.category.name,
            is_primary=ac.is_primary,
        ))

    tags = []
    for at in article.tags:
        tags.append(TagBrief(
            id=at.tag.id,
            name=at.tag.name,
            color=at.tag.color,
        ))

    return ArticleResponse(
        id=article.id,
        source_type=article.source_type,
        original_url=article.original_url,
        title=article.title,
        authors=article.authors or [],
        publication_date=article.publication_date,
        summary=article.summary,
        summary_model=article.summary_model,
        color_id=article.color_id,
        file_path=article.file_path,
        metadata=article.article_metadata or {},
        processing_status=article.processing_status,
        processing_error=article.processing_error,
        word_count=article.word_count,
        reading_time_minutes=calculate_reading_time(article.word_count),
        created_at=article.created_at,
        updated_at=article.updated_at,
        categories=categories,
        tags=tags,
        note_count=len(article.notes) if article.notes else 0,
    )


@router.post("", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article_from_url(
    data: ArticleCreateURL,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new article from a URL"""
    url = str(data.url)

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

        # Load relationships
        result = await db.execute(
            select(Article)
            .where(Article.id == article.id)
            .options(
                selectinload(Article.categories).selectinload(ArticleCategory.category),
                selectinload(Article.tags).selectinload(ArticleTag.tag),
                selectinload(Article.notes),
            )
        )
        article = result.scalar_one()

        return article_to_response(article)

    except Exception as e:
        import traceback
        print(f"ERROR extracting URL {url}:")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract content from URL: {str(e)}",
        )


@router.post("/upload", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article_from_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new article from an uploaded PDF"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Extract content from PDF
        extracted = await extract_content(file_path=temp_path)

        # TODO: Upload to R2 storage and get permanent path
        # For now, we'll store the file path as a placeholder
        file_path = f"uploads/{current_user.id}/{file.filename}"

        # Create article
        article = Article(
            user_id=current_user.id,
            source_type=SourceType.PDF,
            title=extracted.title,
            authors=extracted.authors,
            extracted_text=extracted.text,
            word_count=len(extracted.text.split()) if extracted.text else None,
            file_path=file_path,
            article_metadata=extracted.metadata,
            processing_status=ProcessingStatus.PENDING,
        )

        db.add(article)
        await db.commit()
        await db.refresh(article)

        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)

        # Load relationships
        result = await db.execute(
            select(Article)
            .where(Article.id == article.id)
            .options(
                selectinload(Article.categories).selectinload(ArticleCategory.category),
                selectinload(Article.tags).selectinload(ArticleTag.tag),
                selectinload(Article.notes),
            )
        )
        article = result.scalar_one()

        return article_to_response(article)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process PDF: {str(e)}",
        )


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category_id: UUID | None = None,
    tag_id: UUID | None = None,
    color_id: UUID | None = None,
    status: ProcessingStatus | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List articles with filtering and pagination"""
    # Base query
    query = (
        select(Article)
        .where(Article.user_id == current_user.id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.notes),
        )
    )

    # Apply filters
    if search:
        # Full-text search
        query = query.where(
            or_(
                Article.title.ilike(f"%{search}%"),
                Article.search_vector.match(search),
            )
        )

    if category_id:
        query = query.join(ArticleCategory).where(ArticleCategory.category_id == category_id)

    if tag_id:
        query = query.join(ArticleTag).where(ArticleTag.tag_id == tag_id)

    if color_id:
        query = query.where(Article.color_id == color_id)

    if status:
        query = query.where(Article.processing_status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination and ordering
    query = query.order_by(Article.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    articles = result.scalars().all()

    return ArticleListResponse(
        items=[article_to_response(a) for a in articles],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single article by ID"""
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.notes),
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return article_to_response(article)


@router.get("/{article_id}/text")
async def get_article_text(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the extracted text of an article"""
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return {"text": article.extracted_text}


@router.patch("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: UUID,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an article"""
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    # Update fields
    if data.title is not None:
        article.title = data.title
    if data.color_id is not None:
        article.color_id = data.color_id

    # Update categories if provided
    if data.category_ids is not None:
        # Remove existing categories using DELETE statement
        await db.execute(
            delete(ArticleCategory).where(ArticleCategory.article_id == article_id)
        )

        # Add new categories
        for i, cat_id in enumerate(data.category_ids):
            ac = ArticleCategory(
                article_id=article_id,
                category_id=cat_id,
                is_primary=(i == 0),
            )
            db.add(ac)

    # Update tags if provided
    if data.tag_ids is not None:
        # Remove existing tags using DELETE statement
        await db.execute(
            delete(ArticleTag).where(ArticleTag.article_id == article_id)
        )

        # Add new tags
        for tag_id in data.tag_ids:
            at = ArticleTag(
                article_id=article_id,
                tag_id=tag_id,
            )
            db.add(at)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.notes),
        )
    )
    article = result.scalar_one()

    return article_to_response(article)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an article"""
    result = await db.execute(
        select(Article)
        .where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    # TODO: Delete file from R2 storage if exists

    await db.delete(article)
    await db.commit()


@router.post("/{article_id}/process", response_model=ArticleResponse)
async def process_article(
    article_id: UUID,
    provider_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process an article with AI: generate summary, suggest tags, and categorize.
    This can be called manually or happens automatically after ingestion.
    """
    # Verify article belongs to user
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    try:
        ai_service = AIService(db)
        article = await ai_service.process_article(
            article_id=article_id,
            user_id=current_user.id,
            provider_id=provider_id,
        )

        # Reload with relationships
        result = await db.execute(
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.categories).selectinload(ArticleCategory.category),
                selectinload(Article.tags).selectinload(ArticleTag.tag),
                selectinload(Article.notes),
            )
        )
        article = result.scalar_one()

        return article_to_response(article)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )


@router.post("/{article_id}/reprocess", response_model=ArticleResponse)
async def reprocess_article(
    article_id: UUID,
    provider_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-run AI processing on an article.
    Useful if you want to regenerate the summary with a different model.
    """
    return await process_article(article_id, provider_id, db, current_user)


@router.post("/reorganize")
async def reorganize_articles(
    uncategorized_only: bool = Query(True, description="Only process articles without categories"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reorganize articles by running AI categorization on them.
    This will create new categories as needed and assign articles.
    """
    # Build query for articles to process
    query = (
        select(Article)
        .where(Article.user_id == current_user.id)
        .where(Article.processing_status == ProcessingStatus.COMPLETED)
    )

    if uncategorized_only:
        # Find articles with no category assignments
        from sqlalchemy import not_, exists
        has_category = (
            select(ArticleCategory.article_id)
            .where(ArticleCategory.article_id == Article.id)
            .exists()
        )
        query = query.where(~has_category)

    result = await db.execute(query)
    articles = result.scalars().all()

    if not articles:
        return {
            "message": "No articles to reorganize",
            "processed": 0,
            "categories_created": 0,
        }

    try:
        ai_service = AIService(db)
        processed = 0
        errors = []

        for article in articles:
            try:
                await ai_service.process_article(
                    article_id=article.id,
                    user_id=current_user.id,
                )
                processed += 1
            except Exception as e:
                errors.append(f"{article.title[:50]}: {str(e)}")

        # Count new categories created (those suggested by AI)
        cat_result = await db.execute(
            select(func.count(ArticleCategory.article_id))
            .where(ArticleCategory.suggested_by_ai == True)
        )
        ai_categorized = cat_result.scalar()

        return {
            "message": f"Reorganization complete",
            "processed": processed,
            "total_articles": len(articles),
            "errors": errors[:5] if errors else [],  # Return first 5 errors
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reorganization failed: {str(e)}",
        )


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    data: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ask a question about your saved articles using RAG.
    Searches relevant articles and uses AI to answer based on their content.
    """
    # Get the user's default AI provider
    provider = await get_default_provider(db, current_user.id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI provider configured. Please add one in Settings.",
        )

    # Search for relevant articles using full-text search
    search_terms = data.question
    query = (
        select(Article)
        .where(Article.user_id == current_user.id)
        .where(Article.processing_status == ProcessingStatus.COMPLETED)
        .where(
            or_(
                Article.title.ilike(f"%{search_terms}%"),
                Article.search_vector.match(search_terms),
            )
        )
        .order_by(Article.created_at.desc())
        .limit(5)
    )

    result = await db.execute(query)
    articles = result.scalars().all()

    if not articles:
        # If no matches, get recent articles as fallback
        query = (
            select(Article)
            .where(Article.user_id == current_user.id)
            .where(Article.processing_status == ProcessingStatus.COMPLETED)
            .order_by(Article.created_at.desc())
            .limit(5)
        )
        result = await db.execute(query)
        articles = result.scalars().all()

    if not articles:
        return AskResponse(
            answer="You don't have any processed articles yet. Add some articles and process them first.",
            articles=[],
        )

    # Build context from articles
    context_parts = []
    article_refs = []
    for article in articles:
        # Include title, summary, and excerpt of extracted text
        article_context = f"### {article.title}\n\n"
        if article.summary:
            article_context += f"**Summary:**\n{article.summary}\n\n"
        if article.extracted_text:
            excerpt = truncate_text(article.extracted_text, 3000)
            article_context += f"**Content excerpt:**\n{excerpt}\n"
        context_parts.append(article_context)
        article_refs.append(ArticleReference(id=article.id, title=article.title))

    context = "\n\n---\n\n".join(context_parts)

    try:
        # Get answer from AI
        answer = await provider.answer_question(
            question=data.question,
            context=context,
        )

        return AskResponse(
            answer=answer,
            articles=article_refs,
        )

    except Exception as e:
        logger.error(f"Question answering failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to answer question: {str(e)}",
        )
