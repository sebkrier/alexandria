import logging
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.embeddings import generate_query_embedding
from app.ai.factory import get_default_provider
from app.ai.prompts import METADATA_SYSTEM_PROMPT, truncate_text
from app.ai.query_router import (
    QueryType,
    classify_query,
    detect_metadata_operation,
    execute_metadata_query,
    format_metadata_for_llm,
)
from app.ai.service import AIService
from app.database import get_db
from app.extractors import extract_content
from app.models.article import Article, ProcessingStatus, SourceType
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.user import User
from app.schemas.article import (
    ArticleCreateURL,
    ArticleListResponse,
    ArticleReference,
    ArticleResponse,
    ArticleUpdate,
    AskRequest,
    AskResponse,
    BulkColorRequest,
    BulkColorResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    BulkReanalyzeRequest,
    BulkReanalyzeResponse,
    CategoryBrief,
    TagBrief,
    UnreadListResponse,
    UnreadNavigationResponse,
)
from app.tasks import process_article_background
from app.utils.article_helpers import calculate_reading_time, determine_media_type
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

# Search configuration constants
SEMANTIC_SEARCH_LIMIT = 10  # Max articles from vector similarity search
KEYWORD_SEARCH_LIMIT = 10  # Max articles from full-text/keyword search
MERGED_RESULTS_LIMIT = 15  # Max articles after merging semantic + keyword
FALLBACK_RESULTS_LIMIT = 10  # Max recent articles when no search results
MAX_SEARCH_WORDS = 10  # Max words to extract from query
MAX_MATCH_WORDS = 5  # Max words for title/category/tag matching
MIN_WORD_LENGTH = 3  # Minimum word length for keyword matching

router = APIRouter()


def article_to_response(article: Article) -> ArticleResponse:
    """Convert Article model to response schema"""
    categories = []
    for ac in article.categories:
        categories.append(
            CategoryBrief(
                id=ac.category.id,
                name=ac.category.name,
                is_primary=ac.is_primary,
            )
        )

    tags = []
    for at in article.tags:
        tags.append(
            TagBrief(
                id=at.tag.id,
                name=at.tag.name,
                color=at.tag.color,
            )
        )

    return ArticleResponse(
        id=article.id,
        source_type=article.source_type,
        media_type=determine_media_type(article.source_type, article.original_url),
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
        is_read=article.is_read,
        created_at=article.created_at,
        updated_at=article.updated_at,
        categories=categories,
        tags=tags,
        note_count=len(article.notes) if article.notes else 0,
    )


@router.post("", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article_from_url(
    data: ArticleCreateURL,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleResponse:
    """Create a new article from a URL.

    Extracts content from the provided URL, creates an article record,
    and schedules background AI processing for summarization and tagging.

    Args:
        data: Request body containing the URL to process.
        background_tasks: FastAPI background task manager.
        db: Database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created article with metadata.

    Raises:
        HTTPException: 400 if content extraction fails.
    """
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

        # Schedule AI processing in background
        background_tasks.add_task(process_article_background, article.id, current_user.id)
        logger.info(f"Scheduled background processing for article {article.id}")

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
        logger.exception(f"Failed to extract content from URL: {url}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract content from URL: {str(e)}",
        ) from e


@router.post("/upload", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleResponse:
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

        # Schedule AI processing in background
        background_tasks.add_task(process_article_background, article.id, current_user.id)
        logger.info(f"Scheduled background processing for uploaded PDF {article.id}")

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
        ) from e


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category_id: UUID | None = None,
    tag_id: UUID | None = None,
    color_id: UUID | None = None,
    status: ProcessingStatus | None = None,
    is_read: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleListResponse:
    """List articles with filtering and pagination.

    Supports filtering by category (including subcategories), tags, color,
    processing status, and read status. Full-text search is supported
    via the search parameter.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page (max 100).
        search: Optional full-text search query.
        category_id: Filter by category (includes subcategories).
        tag_id: Filter by tag.
        color_id: Filter by color label.
        status: Filter by processing status.
        is_read: Filter by read/unread status.

    Returns:
        Paginated list of articles with total count.
    """
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
        # Get the category and all its subcategories
        from app.models.category import Category

        # Get all descendant category IDs (for hierarchical filtering)
        async def get_descendant_ids(cat_id: UUID) -> list[UUID]:
            result = await db.execute(select(Category.id).where(Category.parent_id == cat_id))
            child_ids = [row[0] for row in result.all()]
            descendants = list(child_ids)
            for child_id in child_ids:
                descendants.extend(await get_descendant_ids(child_id))
            return descendants

        # Include the category itself plus all descendants
        category_ids = [category_id] + await get_descendant_ids(category_id)
        query = query.join(ArticleCategory).where(ArticleCategory.category_id.in_(category_ids))

    if tag_id:
        query = query.join(ArticleTag).where(ArticleTag.tag_id == tag_id)

    if color_id:
        query = query.where(Article.color_id == color_id)

    if status:
        query = query.where(Article.processing_status == status)

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
) -> ArticleResponse:
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
) -> dict[str, str | None]:
    """Get the extracted text of an article"""
    result = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return {"text": article.extracted_text}


# =============================================================================
# Unread Reader Endpoints
# =============================================================================


@router.get("/unread/list", response_model=UnreadListResponse)
async def get_unread_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadListResponse:
    """Get list of unread article IDs in order (oldest first)"""
    result = await db.execute(
        select(Article.id)
        .where(Article.user_id == current_user.id)
        .where(Article.is_read.is_(False))
        .order_by(Article.created_at.asc())
    )
    article_ids = [row[0] for row in result.all()]

    return UnreadListResponse(
        items=article_ids,
        total=len(article_ids),
    )


@router.get("/unread/navigation/{article_id}", response_model=UnreadNavigationResponse)
async def get_unread_navigation(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadNavigationResponse:
    """Get navigation info for unread reader (prev/next article)"""
    # Get all unread article IDs in order
    result = await db.execute(
        select(Article.id)
        .where(Article.user_id == current_user.id)
        .where(Article.is_read.is_(False))
        .order_by(Article.created_at.asc())
    )
    unread_ids = [row[0] for row in result.all()]

    # Find current position
    current_index = -1
    for i, uid in enumerate(unread_ids):
        if uid == article_id:
            current_index = i
            break

    # If article not in unread list, return position 0
    if current_index == -1:
        return UnreadNavigationResponse(
            current_position=0,
            total_unread=len(unread_ids),
            prev_id=None,
            next_id=unread_ids[0] if unread_ids else None,
        )

    return UnreadNavigationResponse(
        current_position=current_index + 1,
        total_unread=len(unread_ids),
        prev_id=unread_ids[current_index - 1] if current_index > 0 else None,
        next_id=unread_ids[current_index + 1] if current_index < len(unread_ids) - 1 else None,
    )


@router.patch("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: UUID,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleResponse:
    """Update an article"""
    result = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
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
    if data.is_read is not None:
        article.is_read = data.is_read

    # Update categories if provided
    if data.category_ids is not None:
        # Remove existing categories using DELETE statement
        await db.execute(delete(ArticleCategory).where(ArticleCategory.article_id == article_id))

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
        await db.execute(delete(ArticleTag).where(ArticleTag.article_id == article_id))

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
) -> None:
    """Delete an article"""
    result = await db.execute(
        select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
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
) -> ArticleResponse:
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
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        ) from e


@router.post("/{article_id}/reprocess", response_model=ArticleResponse)
async def reprocess_article(
    article_id: UUID,
    provider_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleResponse:
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
) -> dict:
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

        return {
            "message": "Reorganization complete",
            "processed": processed,
            "total_articles": len(articles),
            "errors": errors[:5] if errors else [],  # Return first 5 errors
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reorganization failed: {str(e)}",
        ) from e


# =============================================================================
# Bulk Operations
# =============================================================================


@router.post("/bulk/delete", response_model=BulkDeleteResponse)
async def bulk_delete_articles(
    data: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkDeleteResponse:
    """Delete multiple articles at once"""
    deleted = 0
    failed = []

    for article_id in data.article_ids:
        try:
            result = await db.execute(
                select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
            )
            article = result.scalar_one_or_none()

            if not article:
                failed.append(f"{article_id}: Not found")
                continue

            await db.delete(article)
            deleted += 1

        except Exception as e:
            failed.append(f"{article_id}: {str(e)}")

    await db.commit()

    return BulkDeleteResponse(deleted=deleted, failed=failed)


@router.patch("/bulk/color", response_model=BulkColorResponse)
async def bulk_update_color(
    data: BulkColorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkColorResponse:
    """Update color for multiple articles at once"""
    updated = 0
    failed = []

    for article_id in data.article_ids:
        try:
            result = await db.execute(
                select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
            )
            article = result.scalar_one_or_none()

            if not article:
                failed.append(f"{article_id}: Not found")
                continue

            article.color_id = data.color_id
            updated += 1

        except Exception as e:
            failed.append(f"{article_id}: {str(e)}")

    await db.commit()

    return BulkColorResponse(updated=updated, failed=failed)


@router.post("/bulk/reanalyze", response_model=BulkReanalyzeResponse)
async def bulk_reanalyze_articles(
    data: BulkReanalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkReanalyzeResponse:
    """Re-analyze multiple articles (regenerate summary, tags, categories)"""
    queued = 0
    skipped = 0
    failed = []

    ai_service = AIService(db)

    for article_id in data.article_ids:
        try:
            result = await db.execute(
                select(Article).where(Article.id == article_id, Article.user_id == current_user.id)
            )
            article = result.scalar_one_or_none()

            if not article:
                failed.append(f"{article_id}: Not found")
                continue

            # Skip if already processing
            if article.processing_status == ProcessingStatus.PROCESSING:
                skipped += 1
                continue

            # Process the article (this runs synchronously for simplicity)
            try:
                await ai_service.process_article(
                    article_id=article_id,
                    user_id=current_user.id,
                )
                queued += 1
            except Exception as e:
                failed.append(f"{article.title[:30]}: {str(e)}")

        except Exception as e:
            failed.append(f"{article_id}: {str(e)}")

    return BulkReanalyzeResponse(queued=queued, skipped=skipped, failed=failed)


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    data: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AskResponse:
    """
    Ask a question about your saved articles.
    Automatically routes between:
    - Content queries (RAG): "What do my articles say about X?"
    - Metadata queries (database): "How many articles do I have?"
    """
    # Get the user's default AI provider
    provider = await get_default_provider(db, current_user.id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI provider configured. Please add one in Settings.",
        )

    # Classify the query type
    query_type = classify_query(data.question)
    logger.info(f"Query classified as: {query_type.value}")

    # Route based on query type
    if query_type == QueryType.METADATA:
        return await _handle_metadata_query(db, current_user.id, data.question, provider)
    else:
        return await _handle_content_query(db, current_user.id, data.question, provider)


async def _handle_metadata_query(
    db: AsyncSession,
    user_id,
    question: str,
    provider,
) -> AskResponse:
    """Handle metadata queries by running database queries and formatting with LLM."""
    try:
        # Detect which operation and parameters
        operation, params = detect_metadata_operation(question)
        logger.info(f"Metadata operation: {operation.value}, params: {params}")

        # Execute the database query
        data = await execute_metadata_query(db, user_id, operation, params)

        # Format for LLM
        formatted_data = format_metadata_for_llm(operation, data)

        # Build context for the LLM (metadata as "article context")
        metadata_context = f"{METADATA_SYSTEM_PROMPT}\n\n---\n\n{formatted_data}"

        # Use LLM to create a natural language response
        # Reuse answer_question since it's designed for Q&A with context
        answer = await provider.answer_question(
            question=question,
            context=metadata_context,
        )

        return AskResponse(
            answer=answer,
            articles=[],  # Metadata queries don't reference specific articles
        )

    except Exception as e:
        logger.error(f"Metadata query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process metadata query: {str(e)}",
        ) from e


async def _handle_content_query(
    db: AsyncSession,
    user_id,
    question: str,
    provider,
) -> AskResponse:
    """
    Handle content queries using hybrid search (semantic + keyword).

    Combines:
    1. Semantic search: Find conceptually related articles via embeddings
    2. Keyword search: Find articles with literal term matches

    This ensures we find both articles that discuss related concepts AND
    articles with exact keyword matches.
    """
    from sqlalchemy import func as sqla_func

    from app.models.category import Category
    from app.models.tag import Tag

    logger.info(f"Content query: '{question[:80]}'")

    # =========================================================================
    # STEP 1: Semantic Search (using local EmbeddingGemma model)
    # =========================================================================
    semantic_results: list[tuple[Article, float]] = []

    # Check if pgvector/embeddings are available
    has_embeddings = hasattr(Article, "embedding")

    if has_embeddings:
        try:
            # Generate embedding for the user's question using local model
            query_embedding = generate_query_embedding(question)

            if query_embedding:
                # Semantic search using pgvector cosine distance
                # Lower distance = more similar
                distance = Article.embedding.cosine_distance(query_embedding)

                semantic_query = (
                    select(Article, distance.label("distance"))
                    .where(Article.user_id == user_id)
                    .where(Article.processing_status == ProcessingStatus.COMPLETED)
                    .where(Article.embedding.isnot(None))
                    .order_by(distance)
                    .limit(SEMANTIC_SEARCH_LIMIT)
                )

                result = await db.execute(semantic_query)
                semantic_results = [(row[0], row[1]) for row in result.all()]

                logger.info(f"Semantic search found {len(semantic_results)} articles:")
                for article, dist in semantic_results:
                    logger.info(f"  - [dist={dist:.4f}] {article.title[:60]}")

        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to keyword-only: {e}")

    # =========================================================================
    # STEP 2: Keyword Search (full-text + title + category/tag matching)
    # =========================================================================
    keyword_results: list[tuple[Article, float]] = []

    try:
        # Build search terms
        search_words = question.lower().split()[:MAX_SEARCH_WORDS]
        valid_words = [w for w in search_words if len(w) >= MIN_WORD_LENGTH]

        # Build conditions for keyword matching
        conditions = []

        # Title substring match
        for word in valid_words[:MAX_MATCH_WORDS]:
            conditions.append(Article.title.ilike(f"%{word}%"))

        # Full-text search
        ts_query = sqla_func.plainto_tsquery("english", question)
        conditions.append(Article.search_vector.op("@@")(ts_query))

        # Category name match
        if valid_words:
            category_subq = (
                select(ArticleCategory.article_id)
                .join(Category, Category.id == ArticleCategory.category_id)
                .where(Category.user_id == user_id)
                .where(or_(*[Category.name.ilike(f"%{w}%") for w in valid_words[:MAX_MATCH_WORDS]]))
            )
            conditions.append(Article.id.in_(category_subq))

            # Tag name match
            tag_subq = (
                select(ArticleTag.article_id)
                .join(Tag, Tag.id == ArticleTag.tag_id)
                .where(Tag.user_id == user_id)
                .where(or_(*[Tag.name.ilike(f"%{w}%") for w in valid_words[:MAX_MATCH_WORDS]]))
            )
            conditions.append(Article.id.in_(tag_subq))

        if conditions:
            # ts_rank for relevance scoring
            ts_rank = sqla_func.ts_rank(Article.search_vector, ts_query)

            keyword_query = (
                select(Article, ts_rank.label("rank"))
                .where(Article.user_id == user_id)
                .where(Article.processing_status == ProcessingStatus.COMPLETED)
                .where(or_(*conditions))
                .order_by(ts_rank.desc())
                .limit(KEYWORD_SEARCH_LIMIT)
            )

            result = await db.execute(keyword_query)
            keyword_results = [(row[0], row[1]) for row in result.all()]

            logger.info(f"Keyword search found {len(keyword_results)} articles:")
            for article, rank in keyword_results:
                logger.info(f"  - [rank={rank:.4f}] {article.title[:60]}")

    except Exception as e:
        logger.warning(f"Keyword search failed: {e}")

    # =========================================================================
    # STEP 3: Merge Results (Hybrid Ranking)
    # =========================================================================
    # Combine semantic and keyword results, deduplicate by article ID
    # Prioritize articles that appear in both result sets

    seen_ids = set()
    merged_articles: list[Article] = []

    # Score articles: appearing in both sets gets priority
    article_scores: dict[str, float] = {}

    # Add semantic results (convert distance to score: lower distance = higher score)
    for article, distance in semantic_results:
        article_id = str(article.id)
        # Convert distance (0-2 for cosine) to score (1-0)
        semantic_score = max(0, 1 - distance)
        article_scores[article_id] = article_scores.get(article_id, 0) + semantic_score

    # Add keyword results (rank is already a score, normalize)
    max_rank = max((r for _, r in keyword_results), default=1) or 1
    for article, rank in keyword_results:
        article_id = str(article.id)
        keyword_score = rank / max_rank if max_rank > 0 else 0
        article_scores[article_id] = article_scores.get(article_id, 0) + keyword_score

    # Create lookup for articles
    all_articles = {str(a.id): a for a, _ in semantic_results + keyword_results}

    # Sort by combined score
    sorted_ids = sorted(article_scores.keys(), key=lambda x: article_scores[x], reverse=True)

    for article_id in sorted_ids[:MERGED_RESULTS_LIMIT]:
        if article_id not in seen_ids:
            seen_ids.add(article_id)
            merged_articles.append(all_articles[article_id])

    logger.info(f"Hybrid search merged to {len(merged_articles)} unique articles")

    # =========================================================================
    # STEP 4: Fallback if no results
    # =========================================================================
    if not merged_articles:
        logger.info("No matches found, falling back to recent articles")
        query = (
            select(Article)
            .where(Article.user_id == user_id)
            .where(Article.processing_status == ProcessingStatus.COMPLETED)
            .order_by(Article.created_at.desc())
            .limit(FALLBACK_RESULTS_LIMIT)
        )
        result = await db.execute(query)
        merged_articles = list(result.scalars().all())

    if not merged_articles:
        return AskResponse(
            answer="You don't have any processed articles yet. Add some articles and process them first.",
            articles=[],
        )

    # Build context from articles
    context_parts = []
    article_refs = []
    for article in merged_articles:
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
            question=question,
            context=context,
        )

        return AskResponse(
            answer=answer,
            articles=article_refs,
        )

    except Exception as e:
        logger.error(f"Content query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to answer question: {str(e)}",
        ) from e
