"""Article model to template dict converters."""

from sqlalchemy import inspect

from app.models.article import Article
from app.utils.article_helpers import calculate_reading_time, determine_media_type_str


def article_to_dict(article: Article) -> dict:
    """Convert Article model to a dict for templates."""
    categories = []
    for ac in article.categories:
        categories.append(
            {
                "id": str(ac.category.id),
                "name": ac.category.name,
                "is_primary": ac.is_primary,
            }
        )

    tags = []
    for at in article.tags:
        tags.append(
            {
                "id": str(at.tag.id),
                "name": at.tag.name,
                "color": at.tag.color,
            }
        )

    color = None
    if article.color:
        color = {
            "id": str(article.color.id),
            "hex_value": article.color.hex_value,
            "name": article.color.name,
        }

    # Handle source_type - might be enum or string
    source_type_val = article.source_type
    if hasattr(source_type_val, "value"):
        source_type_str = source_type_val.value
    else:
        source_type_str = str(source_type_val) if source_type_val else "url"

    # Handle processing_status - might be enum or string
    proc_status = article.processing_status
    if hasattr(proc_status, "value"):
        proc_status_str = proc_status.value
    else:
        proc_status_str = str(proc_status) if proc_status else "pending"

    return {
        "id": str(article.id),
        "source_type": source_type_str,
        "media_type": determine_media_type_str(article.source_type, article.original_url),
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


def article_to_detail_dict(article: Article) -> dict:
    """Convert Article model to a detailed dict for article detail template."""
    categories = []
    for ac in article.categories:
        categories.append(
            {
                "id": str(ac.category.id),
                "name": ac.category.name,
                "is_primary": ac.is_primary,
            }
        )

    tags = []
    for at in article.tags:
        tags.append(
            {
                "id": str(at.tag.id),
                "name": at.tag.name,
                "color": at.tag.color,
            }
        )

    color = None
    if article.color:
        color = {
            "id": str(article.color.id),
            "hex_value": article.color.hex_value,
            "name": article.color.name,
        }

    # Handle source_type - might be enum or string
    source_type_val = article.source_type
    if hasattr(source_type_val, "value"):
        source_type_str = source_type_val.value
    else:
        source_type_str = str(source_type_val) if source_type_val else "url"

    # Handle processing_status - might be enum or string
    proc_status = article.processing_status
    if hasattr(proc_status, "value"):
        proc_status_str = proc_status.value
    else:
        proc_status_str = str(proc_status) if proc_status else "pending"

    # Include notes if loaded (check if relationship is actually loaded to avoid lazy load in async)
    notes = []
    insp = inspect(article)
    if "notes" in insp.dict:  # Only access if already loaded
        for note in sorted(article.notes, key=lambda n: n.created_at, reverse=True):
            notes.append(
                {
                    "id": str(note.id),
                    "content": note.content,
                    "created_at": note.created_at,
                }
            )

    return {
        "id": str(article.id),
        "source_type": source_type_str,
        "media_type": determine_media_type_str(article.source_type, article.original_url),
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
        "notes": notes,
        "created_at": article.created_at,
    }
