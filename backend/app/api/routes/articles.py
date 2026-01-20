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

logger = logging.getLogger(__name__)
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
from app.database import async_session_maker, get_db
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
    MediaType,
    TagBrief,
    UnreadListResponse,
    UnreadNavigationResponse,
)
from app.utils.auth import get_current_user
from app.services.article_service import ArticleService, process_article_background_task

router = APIRouter()

def calculate_reading_time(word_count: int | None) -> int | None:
    """Calculate reading time in minutes (200 words per minute)"""
    if word_count is None:
        return None
    return max(1, round(word_count / 200))


def determine_media_type(source_type: SourceType, original_url: str | None) -> MediaType:
    """Determine user-friendly media type from source_type and URL"""
    # Direct mappings from source_type
    if source_type == SourceType.ARXIV:
        return MediaType.PAPER
    if source_type == SourceType.VIDEO:
        return MediaType.VIDEO
    if source_type == SourceType.PDF:
        return MediaType.PDF

    # For URL source type, look at the URL to determine more specific type
    if source_type == SourceType.URL and original_url:
        url_lower = original_url.lower()

        # Newsletter platforms
        if "substack.com" in url_lower or "/p/" in url_lower:
            return MediaType.NEWSLETTER

        # Common blog platforms
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
            return MediaType.BLOG

        # Academic/paper indicators
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
            return MediaType.PAPER

    # Default to article
    return MediaType.ARTICLE


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

    note_count = 0
    if 'notes' in article.__dict__:
        note_count = len(article.notes)

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
        note_count=note_count,
    )


@router.post("", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article_from_url(
    data: ArticleCreateURL,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleResponse:
    service = ArticleService(db)
    try:
        article = await service.create_article_from_url(
            url=str(data.url),
            user_id=current_user.id,
            background_tasks=background_tasks
        )
        return article_to_response(article)
    except Exception as e:
        import traceback
        logger.error(f"ERROR creating article from URL {data.url}: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create article: {str(e)}",
        )


@router.post("/upload", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    try:
        import tempfile
        from pathlib import Path
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

        Path(temp_path).unlink(missing_ok=True)
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
    is_read: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleListResponse:
    service = ArticleService(db)
    articles, total = await service.list_articles(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        tag_id=tag_id,
        color_id=color_id,
        status=status,
        is_read=is_read
    )

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
    service = ArticleService(db)
    article = await service.get_article(article_id, current_user.id)

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


@router.get("/unread/list", response_model=UnreadListResponse)
async def get_unread_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Article.id)
        .where(Article.user_id == current_user.id)
        .where(Article.is_read == False)
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
):
    result = await db.execute(
        select(Article.id)
        .where(Article.user_id == current_user.id)
        .where(Article.is_read == False)
        .order_by(Article.created_at.asc())
    )
    unread_ids = [row[0] for row in result.all()]

    current_index = -1
    for i, uid in enumerate(unread_ids):
        if uid == article_id:
            current_index = i
            break

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
):
    service = ArticleService(db)
    article = await service.update_article(
        article_id=article_id,
        user_id=current_user.id,
        title=data.title,
        color_id=data.color_id,
        is_read=data.is_read,
        category_ids=data.category_ids,
        tag_ids=data.tag_ids
    )

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return article_to_response(article)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(db)
    success = await service.delete_article(article_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )


@router.post("/{article_id}/process", response_model=ArticleResponse)
async def process_article(
    article_id: UUID,
    provider_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    return await process_article(article_id, provider_id, db, current_user)

@router.post("/reorganize")
async def reorganize_articles(
    uncategorized_only: bool = Query(True, description="Only process articles without categories"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Article)
        .where(Article.user_id == current_user.id)
        .where(Article.processing_status == ProcessingStatus.COMPLETED)
    )

    if uncategorized_only:
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
            "errors": errors[:5] if errors else [],
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

@router.post("/bulk/delete", response_model=BulkDeleteResponse)
async def bulk_delete_articles(
    data: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
):
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
):
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

            if article.processing_status == ProcessingStatus.PROCESSING:
                skipped += 1
                continue

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
):
    provider = await get_default_provider(db, current_user.id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI provider configured. Please add one in Settings.",
        )

    query_type = classify_query(data.question)
    logger.info(f"Query classified as: {query_type.value}")

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
    try:
        operation, params = detect_metadata_operation(question)
        logger.info(f"Metadata operation: {operation.value}, params: {params}")

        data = await execute_metadata_query(db, user_id, operation, params)
        formatted_data = format_metadata_for_llm(operation, data)
        metadata_context = f"{METADATA_SYSTEM_PROMPT}\n\n---\n\n{formatted_data}"

        answer = await provider.answer_question(
            question=question,
            context=metadata_context,
        )

        return AskResponse(
            answer=answer,
            articles=[],
        )

    except Exception as e:
        logger.error(f"Metadata query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process metadata query: {str(e)}",
        )


async def _handle_content_query(
    db: AsyncSession,
    user_id,
    question: str,
    provider,
) -> AskResponse:
    from sqlalchemy import func as sqla_func
    from app.models.category import Category
    from app.models.tag import Tag

    logger.info(f"Content query: '{question[:80]}'")

    semantic_results: list[tuple[Article, float]] = []
    has_embeddings = hasattr(Article, "embedding")

    if has_embeddings:
        try:
            query_embedding = generate_query_embedding(question)

            if query_embedding:
                distance = Article.embedding.cosine_distance(query_embedding)
                semantic_query = (
                    select(Article, distance.label("distance"))
                    .where(Article.user_id == user_id)
                    .where(Article.processing_status == ProcessingStatus.COMPLETED)
                    .where(Article.embedding.isnot(None))
                    .order_by(distance)
                    .limit(10)
                )

                result = await db.execute(semantic_query)
                semantic_results = [(row[0], row[1]) for row in result.all()]
        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to keyword-only: {e}")

    keyword_results: list[tuple[Article, float]] = []

    try:
        search_words = question.lower().split()[:10]
        valid_words = [w for w in search_words if len(w) >= 3]

        conditions = []
        for word in valid_words[:5]:
            conditions.append(Article.title.ilike(f"%{word}%"))

        ts_query = sqla_func.plainto_tsquery("english", question)
        conditions.append(Article.search_vector.op("@@")(ts_query))

        if valid_words:
            category_subq = (
                select(ArticleCategory.article_id)
                .join(Category, Category.id == ArticleCategory.category_id)
                .where(Category.user_id == user_id)
                .where(or_(*[Category.name.ilike(f"%{w}%") for w in valid_words[:5]]))
            )
            conditions.append(Article.id.in_(category_subq))

            tag_subq = (
                select(ArticleTag.article_id)
                .join(Tag, Tag.id == ArticleTag.tag_id)
                .where(Tag.user_id == user_id)
                .where(or_(*[Tag.name.ilike(f"%{w}%") for w in valid_words[:5]]))
            )
            conditions.append(Article.id.in_(tag_subq))

        if conditions:
            ts_rank = sqla_func.ts_rank(Article.search_vector, ts_query)

            keyword_query = (
                select(Article, ts_rank.label("rank"))
                .where(Article.user_id == user_id)
                .where(Article.processing_status == ProcessingStatus.COMPLETED)
                .where(or_(*conditions))
                .order_by(ts_rank.desc())
                .limit(10)
            )

            result = await db.execute(keyword_query)
            keyword_results = [(row[0], row[1]) for row in result.all()]

    except Exception as e:
        logger.warning(f"Keyword search failed: {e}")

    seen_ids = set()
    merged_articles: list[Article] = []
    article_scores: dict[str, float] = {}

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

    for article_id in sorted_ids[:15]:
        if article_id not in seen_ids:
            seen_ids.add(article_id)
            merged_articles.append(all_articles[article_id])

    if not merged_articles:
        query = (
            select(Article)
            .where(Article.user_id == user_id)
            .where(Article.processing_status == ProcessingStatus.COMPLETED)
            .order_by(Article.created_at.desc())
            .limit(10)
        )
        result = await db.execute(query)
        merged_articles = list(result.scalars().all())

    if not merged_articles:
        return AskResponse(
            answer="You don't have any processed articles yet. Add some articles and process them first.",
            articles=[],
        )

    context_parts = []
    article_refs = []
    for article in merged_articles:
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
        )
