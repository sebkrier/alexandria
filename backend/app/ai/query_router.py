"""
Query routing for the Ask feature.
Classifies queries as content (RAG) or metadata (database) and routes accordingly.
"""

import re
import logging
from enum import Enum
from datetime import datetime, timedelta
from uuid import UUID
from typing import Any

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, ProcessingStatus
from app.models.category import Category
from app.models.tag import Tag
from app.models.article_category import ArticleCategory
from app.models.article_tag import ArticleTag

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    CONTENT = "content"  # Questions about article content → RAG
    METADATA = "metadata"  # Questions about the library → database queries


class MetadataOperation(str, Enum):
    """Supported metadata operations"""
    TOTAL_COUNT = "total_count"
    COUNT_BY_CATEGORY = "count_by_category"
    COUNT_BY_TAG = "count_by_tag"
    COUNT_BY_MEDIA_TYPE = "count_by_media_type"
    COUNT_BY_COLOR = "count_by_color"
    LIST_CATEGORIES = "list_categories"
    LIST_TAGS = "list_tags"
    ARTICLES_IN_DATE_RANGE = "articles_in_date_range"
    RECENT_ARTICLES = "recent_articles"
    TOP_SOURCES = "top_sources"
    LIBRARY_SUMMARY = "library_summary"


# Patterns that indicate metadata queries
METADATA_PATTERNS = [
    # Count patterns
    r"\bhow many\b",
    r"\bcount\b",
    r"\bnumber of\b",
    r"\btotal\b",

    # List patterns
    r"\blist all\b",
    r"\bshow all\b",
    r"\bwhat are my\b",
    r"\bwhat (categories|tags|colors)\b",

    # Aggregate patterns
    r"\bmost common\b",
    r"\bmost frequent\b",
    r"\bmost used\b",
    r"\btop \d+\b",

    # Date patterns without content
    r"\bfrom (last|this) (week|month|year)\b",
    r"\barticles? (added|saved|from)\b.*\b(today|yesterday|last|this)\b",

    # Library overview
    r"\blibrary (summary|overview|stats|statistics)\b",
    r"\bsummarize my library\b",
    r"\boverview of my\b",
]

# Keywords that strongly indicate content queries (even with metadata words)
CONTENT_INDICATORS = [
    r"\babout\b",
    r"\brelated to\b",
    r"\bconcerning\b",
    r"\bon the topic of\b",
    r"\bwhat do.*(say|mention|discuss)\b",
    r"\bsummarize.*(content|articles about)\b",
    r"\bfind.*(arguments?|information|details)\b",
]


def classify_query(question: str) -> QueryType:
    """
    Classify a question as content (RAG) or metadata (database) query.
    Uses rule-based heuristics. Can be upgraded to LLM classification if needed.
    """
    question_lower = question.lower().strip()

    # Check for strong content indicators first
    for pattern in CONTENT_INDICATORS:
        if re.search(pattern, question_lower):
            logger.debug(f"Query classified as CONTENT (indicator: {pattern})")
            return QueryType.CONTENT

    # Check for metadata patterns
    for pattern in METADATA_PATTERNS:
        if re.search(pattern, question_lower):
            logger.debug(f"Query classified as METADATA (pattern: {pattern})")
            return QueryType.METADATA

    # Default to content query (RAG)
    logger.debug("Query classified as CONTENT (default)")
    return QueryType.CONTENT


def detect_metadata_operation(question: str) -> tuple[MetadataOperation, dict[str, Any]]:
    """
    Detect which metadata operation to perform and extract parameters.
    Returns (operation, params) tuple.
    """
    question_lower = question.lower().strip()

    # Library summary/overview
    if re.search(r"\b(library|collection)\b.*(summary|overview|stats)", question_lower):
        return MetadataOperation.LIBRARY_SUMMARY, {}
    if re.search(r"\b(summarize|overview of)\b.*\b(library|articles)\b", question_lower):
        return MetadataOperation.LIBRARY_SUMMARY, {}

    # Total count
    if re.search(r"\bhow many (articles?|items?)\b", question_lower):
        # Check if it's asking about a specific category/tag
        if re.search(r"\bin\b.*\b(category|folder)\b", question_lower):
            return MetadataOperation.COUNT_BY_CATEGORY, {}
        if re.search(r"\bwith\b.*\btag\b", question_lower):
            return MetadataOperation.COUNT_BY_TAG, {}
        return MetadataOperation.TOTAL_COUNT, {}

    # List categories
    if re.search(r"\b(list|show|what are)\b.*\bcategor", question_lower):
        return MetadataOperation.LIST_CATEGORIES, {}

    # List tags
    if re.search(r"\b(list|show|what are)\b.*\btags?\b", question_lower):
        return MetadataOperation.LIST_TAGS, {}

    # Count by media type
    if re.search(r"\bhow many\b.*(papers?|videos?|pdfs?|articles?|newsletters?|blogs?)", question_lower):
        return MetadataOperation.COUNT_BY_MEDIA_TYPE, {}
    if re.search(r"\b(breakdown|distribution)\b.*\b(type|media|source)", question_lower):
        return MetadataOperation.COUNT_BY_MEDIA_TYPE, {}

    # Date range queries
    if re.search(r"\b(last|this|past)\s+(week|month|year)\b", question_lower):
        match = re.search(r"\b(last|this|past)\s+(week|month|year)\b", question_lower)
        period = match.group(2)
        days = {"week": 7, "month": 30, "year": 365}.get(period, 7)
        return MetadataOperation.ARTICLES_IN_DATE_RANGE, {"days": days}

    # Recent articles
    if re.search(r"\b(recent|latest|newest)\b.*\barticles?\b", question_lower):
        return MetadataOperation.RECENT_ARTICLES, {"limit": 10}

    # Top sources/domains
    if re.search(r"\b(top|most (common|used|frequent))\b.*\b(sources?|domains?|sites?)\b", question_lower):
        return MetadataOperation.TOP_SOURCES, {"limit": 10}

    # Count by category (fallback)
    if re.search(r"\bcategor", question_lower):
        return MetadataOperation.COUNT_BY_CATEGORY, {}

    # Count by tag (fallback)
    if re.search(r"\btag", question_lower):
        return MetadataOperation.COUNT_BY_TAG, {}

    # Default to library summary
    return MetadataOperation.LIBRARY_SUMMARY, {}


async def execute_metadata_query(
    db: AsyncSession,
    user_id: UUID,
    operation: MetadataOperation,
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute a metadata query and return structured results.
    """

    if operation == MetadataOperation.TOTAL_COUNT:
        result = await db.execute(
            select(func.count(Article.id))
            .where(Article.user_id == user_id)
        )
        count = result.scalar()
        return {"total_articles": count}

    elif operation == MetadataOperation.COUNT_BY_CATEGORY:
        result = await db.execute(
            select(Category.name, func.count(ArticleCategory.article_id))
            .join(ArticleCategory, Category.id == ArticleCategory.category_id)
            .join(Article, Article.id == ArticleCategory.article_id)
            .where(Article.user_id == user_id)
            .group_by(Category.name)
            .order_by(func.count(ArticleCategory.article_id).desc())
        )
        counts = [{"category": row[0], "count": row[1]} for row in result.all()]
        return {"categories": counts}

    elif operation == MetadataOperation.COUNT_BY_TAG:
        result = await db.execute(
            select(Tag.name, func.count(ArticleTag.article_id))
            .join(ArticleTag, Tag.id == ArticleTag.tag_id)
            .join(Article, Article.id == ArticleTag.article_id)
            .where(Article.user_id == user_id)
            .group_by(Tag.name)
            .order_by(func.count(ArticleTag.article_id).desc())
        )
        counts = [{"tag": row[0], "count": row[1]} for row in result.all()]
        return {"tags": counts}

    elif operation == MetadataOperation.COUNT_BY_MEDIA_TYPE:
        result = await db.execute(
            select(Article.source_type, func.count(Article.id))
            .where(Article.user_id == user_id)
            .group_by(Article.source_type)
            .order_by(func.count(Article.id).desc())
        )
        counts = [{"type": row[0].value if hasattr(row[0], 'value') else str(row[0]), "count": row[1]} for row in result.all()]
        return {"media_types": counts}

    elif operation == MetadataOperation.LIST_CATEGORIES:
        result = await db.execute(
            select(Category.name, Category.parent_id, func.count(ArticleCategory.article_id))
            .outerjoin(ArticleCategory, Category.id == ArticleCategory.category_id)
            .where(Category.user_id == user_id)
            .group_by(Category.id, Category.name, Category.parent_id)
            .order_by(Category.name)
        )
        categories = []
        for row in result.all():
            categories.append({
                "name": row[0],
                "is_subcategory": row[1] is not None,
                "article_count": row[2] or 0,
            })
        return {"categories": categories, "total_categories": len(categories)}

    elif operation == MetadataOperation.LIST_TAGS:
        result = await db.execute(
            select(Tag.name, func.count(ArticleTag.article_id))
            .outerjoin(ArticleTag, Tag.id == ArticleTag.tag_id)
            .where(Tag.user_id == user_id)
            .group_by(Tag.id, Tag.name)
            .order_by(func.count(ArticleTag.article_id).desc())
        )
        tags = [{"name": row[0], "article_count": row[1] or 0} for row in result.all()]
        return {"tags": tags, "total_tags": len(tags)}

    elif operation == MetadataOperation.ARTICLES_IN_DATE_RANGE:
        days = params.get("days", 7)
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(func.count(Article.id))
            .where(Article.user_id == user_id)
            .where(Article.created_at >= cutoff)
        )
        count = result.scalar()

        # Also get some details about recent articles
        recent_result = await db.execute(
            select(Article.title, Article.created_at)
            .where(Article.user_id == user_id)
            .where(Article.created_at >= cutoff)
            .order_by(Article.created_at.desc())
            .limit(10)
        )
        recent = [{"title": row[0], "date": row[1].strftime("%Y-%m-%d")} for row in recent_result.all()]

        return {
            "count": count,
            "period_days": days,
            "recent_articles": recent,
        }

    elif operation == MetadataOperation.RECENT_ARTICLES:
        limit = params.get("limit", 10)
        result = await db.execute(
            select(Article.title, Article.created_at, Article.source_type)
            .where(Article.user_id == user_id)
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        articles = [
            {
                "title": row[0],
                "date": row[1].strftime("%Y-%m-%d"),
                "type": row[2].value if hasattr(row[2], 'value') else str(row[2]),
            }
            for row in result.all()
        ]
        return {"recent_articles": articles}

    elif operation == MetadataOperation.TOP_SOURCES:
        limit = params.get("limit", 10)
        # Extract domain from URL
        result = await db.execute(
            select(Article.original_url)
            .where(Article.user_id == user_id)
            .where(Article.original_url.isnot(None))
        )

        # Count domains
        from urllib.parse import urlparse
        domain_counts: dict[str, int] = {}
        for row in result.all():
            url = row[0]
            if url:
                try:
                    domain = urlparse(url).netloc
                    # Remove www. prefix
                    if domain.startswith("www."):
                        domain = domain[4:]
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                except:
                    pass

        # Sort by count
        sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        sources = [{"domain": d, "count": c} for d, c in sorted_domains]
        return {"top_sources": sources}

    elif operation == MetadataOperation.LIBRARY_SUMMARY:
        # Comprehensive library summary
        total_result = await db.execute(
            select(func.count(Article.id))
            .where(Article.user_id == user_id)
        )
        total_articles = total_result.scalar()

        # Count by status
        status_result = await db.execute(
            select(Article.processing_status, func.count(Article.id))
            .where(Article.user_id == user_id)
            .group_by(Article.processing_status)
        )
        status_counts = {row[0].value: row[1] for row in status_result.all()}

        # Count by source type
        type_result = await db.execute(
            select(Article.source_type, func.count(Article.id))
            .where(Article.user_id == user_id)
            .group_by(Article.source_type)
        )
        type_counts = {row[0].value: row[1] for row in type_result.all()}

        # Total categories and tags
        cat_result = await db.execute(
            select(func.count(Category.id))
            .where(Category.user_id == user_id)
        )
        total_categories = cat_result.scalar()

        tag_result = await db.execute(
            select(func.count(Tag.id))
            .where(Tag.user_id == user_id)
        )
        total_tags = tag_result.scalar()

        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await db.execute(
            select(func.count(Article.id))
            .where(Article.user_id == user_id)
            .where(Article.created_at >= week_ago)
        )
        added_this_week = recent_result.scalar()

        return {
            "total_articles": total_articles,
            "status_breakdown": status_counts,
            "type_breakdown": type_counts,
            "total_categories": total_categories,
            "total_tags": total_tags,
            "added_this_week": added_this_week,
        }

    # Fallback
    return {"error": "Unknown operation"}


def format_metadata_for_llm(operation: MetadataOperation, data: dict[str, Any]) -> str:
    """
    Format metadata query results for the LLM to create a natural language response.
    """
    lines = ["## Library Metadata Query Results\n"]

    if operation == MetadataOperation.TOTAL_COUNT:
        lines.append(f"Total articles in library: {data.get('total_articles', 0)}")

    elif operation == MetadataOperation.COUNT_BY_CATEGORY:
        lines.append("Articles by category:")
        for cat in data.get("categories", []):
            lines.append(f"- {cat['category']}: {cat['count']} articles")
        if not data.get("categories"):
            lines.append("No categories found.")

    elif operation == MetadataOperation.COUNT_BY_TAG:
        lines.append("Articles by tag:")
        for tag in data.get("tags", [])[:15]:  # Limit to top 15
            lines.append(f"- {tag['tag']}: {tag['count']} articles")
        if not data.get("tags"):
            lines.append("No tags found.")

    elif operation == MetadataOperation.COUNT_BY_MEDIA_TYPE:
        lines.append("Articles by type:")
        for t in data.get("media_types", []):
            lines.append(f"- {t['type']}: {t['count']} articles")

    elif operation == MetadataOperation.LIST_CATEGORIES:
        lines.append(f"Total categories: {data.get('total_categories', 0)}")
        lines.append("\nCategories:")
        for cat in data.get("categories", []):
            prefix = "  └─ " if cat.get("is_subcategory") else "- "
            lines.append(f"{prefix}{cat['name']} ({cat['article_count']} articles)")

    elif operation == MetadataOperation.LIST_TAGS:
        lines.append(f"Total tags: {data.get('total_tags', 0)}")
        lines.append("\nTags (sorted by usage):")
        for tag in data.get("tags", [])[:20]:  # Limit to top 20
            lines.append(f"- {tag['name']} ({tag['article_count']} articles)")

    elif operation == MetadataOperation.ARTICLES_IN_DATE_RANGE:
        period = data.get("period_days", 7)
        lines.append(f"Articles added in the last {period} days: {data.get('count', 0)}")
        if data.get("recent_articles"):
            lines.append("\nRecent additions:")
            for a in data.get("recent_articles", []):
                lines.append(f"- {a['title']} ({a['date']})")

    elif operation == MetadataOperation.RECENT_ARTICLES:
        lines.append("Most recently added articles:")
        for a in data.get("recent_articles", []):
            lines.append(f"- {a['title']} ({a['type']}, {a['date']})")

    elif operation == MetadataOperation.TOP_SOURCES:
        lines.append("Most common sources/domains:")
        for s in data.get("top_sources", []):
            lines.append(f"- {s['domain']}: {s['count']} articles")

    elif operation == MetadataOperation.LIBRARY_SUMMARY:
        lines.append(f"**Total Articles:** {data.get('total_articles', 0)}")
        lines.append(f"**Added This Week:** {data.get('added_this_week', 0)}")
        lines.append(f"**Categories:** {data.get('total_categories', 0)}")
        lines.append(f"**Tags:** {data.get('total_tags', 0)}")

        if data.get("type_breakdown"):
            lines.append("\n**By Type:**")
            for t, c in data["type_breakdown"].items():
                lines.append(f"- {t}: {c}")

        if data.get("status_breakdown"):
            lines.append("\n**By Status:**")
            for s, c in data["status_breakdown"].items():
                lines.append(f"- {s}: {c}")

    return "\n".join(lines)
