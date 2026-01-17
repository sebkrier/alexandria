"""Library export/import endpoints for backing up and restoring user data."""

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.article import Article
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag
from app.models.category import Category
from app.models.note import Note
from app.models.tag import Tag
from app.models.user import User
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Export Schemas
# =============================================================================


class NoteExport(BaseModel):
    content: str
    created_at: str
    updated_at: str


class ArticleExport(BaseModel):
    original_url: str | None
    title: str
    authors: list[str] | None
    publication_date: str | None
    source_type: str
    summary: str | None
    summary_model: str | None
    extracted_text: str | None
    word_count: int | None
    is_read: bool
    metadata: dict[str, Any] | None
    category_names: list[str]
    tag_names: list[str]
    notes: list[NoteExport]
    created_at: str
    updated_at: str


class CategoryExport(BaseModel):
    name: str
    parent_name: str | None
    description: str | None
    position: int


class TagExport(BaseModel):
    name: str
    color: str | None


class LibraryExport(BaseModel):
    version: str = "1.0"
    exported_at: str
    categories: list[CategoryExport]
    tags: list[TagExport]
    articles: list[ArticleExport]


class ImportStats(BaseModel):
    categories_created: int
    categories_skipped: int
    tags_created: int
    tags_skipped: int
    articles_created: int
    articles_skipped: int
    notes_created: int
    errors: list[str]


# =============================================================================
# Export Endpoint
# =============================================================================


@router.get("/export", response_class=StreamingResponse)
async def export_library(
    include_text: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export the entire library as a JSON file.

    Args:
        include_text: Whether to include full extracted text (larger file size).

    Returns:
        JSON file download with all articles, categories, tags, and notes.
    """
    logger.info(f"Exporting library for user {current_user.id}")

    # Fetch all categories
    result = await db.execute(
        select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.position)
    )
    categories = result.scalars().all()

    # Build category lookup for parent names
    category_lookup = {cat.id: cat for cat in categories}

    categories_export = []
    for cat in categories:
        parent_name = None
        if cat.parent_id and cat.parent_id in category_lookup:
            parent_name = category_lookup[cat.parent_id].name

        categories_export.append(
            CategoryExport(
                name=cat.name,
                parent_name=parent_name,
                description=cat.description,
                position=cat.position,
            )
        )

    # Fetch all tags
    result = await db.execute(
        select(Tag)
        .where(Tag.user_id == current_user.id)
        .order_by(Tag.name)
    )
    tags = result.scalars().all()

    tags_export = [
        TagExport(name=tag.name, color=tag.color)
        for tag in tags
    ]

    # Build tag lookup by ID
    tag_lookup = {tag.id: tag.name for tag in tags}

    # Fetch all articles with relationships
    result = await db.execute(
        select(Article)
        .where(Article.user_id == current_user.id)
        .options(
            selectinload(Article.categories).selectinload(ArticleCategory.category),
            selectinload(Article.tags).selectinload(ArticleTag.tag),
            selectinload(Article.notes),
        )
        .order_by(Article.created_at)
    )
    articles = result.scalars().all()

    articles_export = []
    for article in articles:
        # Get category names
        category_names = [
            ac.category.name for ac in article.categories
            if ac.category is not None
        ]

        # Get tag names
        tag_names = [
            at.tag.name for at in article.tags
            if at.tag is not None
        ]

        # Get notes
        notes_export = [
            NoteExport(
                content=note.content,
                created_at=note.created_at.isoformat(),
                updated_at=note.updated_at.isoformat(),
            )
            for note in (article.notes or [])
        ]

        articles_export.append(
            ArticleExport(
                original_url=article.original_url,
                title=article.title,
                authors=article.authors,
                publication_date=article.publication_date.isoformat() if article.publication_date else None,
                source_type=article.source_type.value if hasattr(article.source_type, 'value') else (article.source_type or "url"),
                summary=article.summary,
                summary_model=article.summary_model,
                extracted_text=article.extracted_text if include_text else None,
                word_count=article.word_count,
                is_read=article.is_read,
                metadata=article.article_metadata,
                category_names=category_names,
                tag_names=tag_names,
                notes=notes_export,
                created_at=article.created_at.isoformat(),
                updated_at=article.updated_at.isoformat(),
            )
        )

    # Build export object
    export_data = LibraryExport(
        version="1.0",
        exported_at=datetime.utcnow().isoformat(),
        categories=categories_export,
        tags=tags_export,
        articles=articles_export,
    )

    # Convert to JSON
    json_content = export_data.model_dump_json(indent=2)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"alexandria_backup_{timestamp}.json"

    logger.info(
        f"Export complete: {len(categories_export)} categories, "
        f"{len(tags_export)} tags, {len(articles_export)} articles"
    )

    # Return as downloadable file
    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# =============================================================================
# Import Endpoint
# =============================================================================


@router.post("/import", response_model=ImportStats)
async def import_library(
    file: UploadFile = File(...),
    merge: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import a library backup JSON file.

    Args:
        file: JSON file from a previous export.
        merge: If True, skip existing items. If False, raise error on duplicates.

    Returns:
        Statistics about what was imported.
    """
    logger.info(f"Importing library for user {current_user.id}")

    # Validate file type
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a JSON file",
        )

    # Read and parse file
    try:
        content = await file.read()
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON file: {str(e)}",
        )

    # Validate structure
    if "version" not in data or "articles" not in data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid backup file format",
        )

    stats = ImportStats(
        categories_created=0,
        categories_skipped=0,
        tags_created=0,
        tags_skipped=0,
        articles_created=0,
        articles_skipped=0,
        notes_created=0,
        errors=[],
    )

    # Get existing data for duplicate checking
    result = await db.execute(
        select(Category).where(Category.user_id == current_user.id)
    )
    existing_categories = {cat.name: cat for cat in result.scalars().all()}

    result = await db.execute(
        select(Tag).where(Tag.user_id == current_user.id)
    )
    existing_tags = {tag.name: tag for tag in result.scalars().all()}

    result = await db.execute(
        select(Article.original_url)
        .where(Article.user_id == current_user.id)
        .where(Article.original_url.isnot(None))
    )
    existing_urls = {row[0] for row in result.all()}

    # Import categories (first pass - create all, second pass - set parents)
    category_map: dict[str, Category] = {}  # name -> Category object

    for cat_data in data.get("categories", []):
        name = cat_data.get("name")
        if not name:
            continue

        if name in existing_categories:
            category_map[name] = existing_categories[name]
            stats.categories_skipped += 1
            continue

        category = Category(
            user_id=current_user.id,
            name=name,
            description=cat_data.get("description"),
            position=cat_data.get("position", 0),
        )
        db.add(category)
        category_map[name] = category
        stats.categories_created += 1

    # Flush to get IDs
    await db.flush()

    # Set parent relationships
    for cat_data in data.get("categories", []):
        name = cat_data.get("name")
        parent_name = cat_data.get("parent_name")

        if name and parent_name and name in category_map and parent_name in category_map:
            category_map[name].parent_id = category_map[parent_name].id

    # Import tags
    tag_map: dict[str, Tag] = {}  # name -> Tag object

    for tag_data in data.get("tags", []):
        name = tag_data.get("name")
        if not name:
            continue

        if name in existing_tags:
            tag_map[name] = existing_tags[name]
            stats.tags_skipped += 1
            continue

        tag = Tag(
            user_id=current_user.id,
            name=name,
            color=tag_data.get("color"),
        )
        db.add(tag)
        tag_map[name] = tag
        stats.tags_created += 1

    # Flush to get IDs
    await db.flush()

    # Import articles
    from app.models.article import ProcessingStatus, SourceType

    for article_data in data.get("articles", []):
        try:
            url = article_data.get("original_url")
            title = article_data.get("title", "Untitled")

            # Skip duplicates by URL
            if url and url in existing_urls:
                stats.articles_skipped += 1
                continue

            # Parse source type
            source_type_str = article_data.get("source_type", "url")
            try:
                source_type = SourceType(source_type_str)
            except ValueError:
                source_type = SourceType.URL

            # Parse publication date
            pub_date = None
            if article_data.get("publication_date"):
                try:
                    pub_date = datetime.fromisoformat(article_data["publication_date"])
                except (ValueError, TypeError):
                    pass

            # Create article
            article = Article(
                user_id=current_user.id,
                source_type=source_type,
                original_url=url,
                title=title,
                authors=article_data.get("authors"),
                publication_date=pub_date,
                summary=article_data.get("summary"),
                summary_model=article_data.get("summary_model"),
                extracted_text=article_data.get("extracted_text", ""),
                word_count=article_data.get("word_count"),
                is_read=article_data.get("is_read", False),
                article_metadata=article_data.get("metadata"),
                processing_status=ProcessingStatus.COMPLETED if article_data.get("summary") else ProcessingStatus.PENDING,
            )
            db.add(article)
            await db.flush()

            # Add category associations
            for cat_name in article_data.get("category_names", []):
                if cat_name in category_map:
                    ac = ArticleCategory(
                        article_id=article.id,
                        category_id=category_map[cat_name].id,
                        is_primary=(cat_name == article_data.get("category_names", [None])[0]),
                    )
                    db.add(ac)

            # Add tag associations
            for tag_name in article_data.get("tag_names", []):
                if tag_name in tag_map:
                    at = ArticleTag(
                        article_id=article.id,
                        tag_id=tag_map[tag_name].id,
                    )
                    db.add(at)

            # Add notes
            for note_data in article_data.get("notes", []):
                note = Note(
                    article_id=article.id,
                    content=note_data.get("content", ""),
                )
                db.add(note)
                stats.notes_created += 1

            if url:
                existing_urls.add(url)
            stats.articles_created += 1

        except Exception as e:
            error_msg = f"Failed to import article '{article_data.get('title', 'Unknown')}': {str(e)}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            if len(stats.errors) > 10:
                stats.errors.append("... and more errors")
                break

    # Commit all changes
    await db.commit()

    logger.info(
        f"Import complete: {stats.categories_created} categories, "
        f"{stats.tags_created} tags, {stats.articles_created} articles, "
        f"{stats.notes_created} notes"
    )

    return stats
