from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, HttpUrl

from app.models.article import ProcessingStatus, SourceType


class MediaType(str, Enum):
    """User-friendly media type for display purposes"""

    ARTICLE = "article"
    PAPER = "paper"
    VIDEO = "video"
    BLOG = "blog"
    PDF = "pdf"
    NEWSLETTER = "newsletter"


class ArticleCreateURL(BaseModel):
    """Schema for creating an article from a URL"""

    url: HttpUrl


class ArticleCreate(BaseModel):
    """Internal schema for creating an article"""

    source_type: SourceType
    original_url: str | None = None
    title: str
    authors: list[str] = []
    publication_date: datetime | None = None
    extracted_text: str
    file_path: str | None = None
    metadata: dict = {}


class ArticleUpdate(BaseModel):
    """Schema for updating an article"""

    title: str | None = None
    color_id: UUID | None = None
    category_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    is_read: bool | None = None


class ArticleSummary(BaseModel):
    """Embedded summary in article response"""

    abstract: str | None = None
    key_contributions: list[str] = []
    methodology: str | None = None
    findings: list[str] = []
    limitations: str | None = None
    relevance_note: str | None = None


class ArticleResponse(BaseModel):
    """Schema for article responses"""

    id: UUID
    source_type: SourceType
    media_type: MediaType  # Computed from source_type + URL
    original_url: str | None
    title: str
    authors: list[str]
    publication_date: datetime | None
    summary: str | None
    summary_model: str | None
    color_id: UUID | None
    file_path: str | None
    metadata: dict
    processing_status: ProcessingStatus
    processing_error: str | None
    word_count: int | None
    reading_time_minutes: int | None
    is_read: bool
    created_at: datetime
    updated_at: datetime

    # Related data (populated separately)
    categories: list["CategoryBrief"] = []
    tags: list["TagBrief"] = []
    note_count: int = 0

    class Config:
        from_attributes = True


class CategoryBrief(BaseModel):
    """Brief category info for article responses"""

    id: UUID
    name: str
    is_primary: bool = False


class TagBrief(BaseModel):
    """Brief tag info for article responses"""

    id: UUID
    name: str
    color: str | None


class ArticleListResponse(BaseModel):
    """Schema for paginated article list"""

    items: list[ArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AskRequest(BaseModel):
    """Schema for asking a question about articles"""

    question: str


class ArticleReference(BaseModel):
    """Brief article reference in ask response"""

    id: UUID
    title: str


class AskResponse(BaseModel):
    """Schema for ask response"""

    answer: str
    articles: list[ArticleReference]


# Bulk operation schemas
class BulkDeleteRequest(BaseModel):
    """Schema for bulk delete request"""

    article_ids: list[UUID]


class BulkDeleteResponse(BaseModel):
    """Schema for bulk delete response"""

    deleted: int
    failed: list[str] = []


class BulkColorRequest(BaseModel):
    """Schema for bulk color update request"""

    article_ids: list[UUID]
    color_id: UUID | None  # None to clear color


class BulkColorResponse(BaseModel):
    """Schema for bulk color update response"""

    updated: int
    failed: list[str] = []


class BulkReanalyzeRequest(BaseModel):
    """Schema for bulk re-analyze request"""

    article_ids: list[UUID]


class BulkReanalyzeResponse(BaseModel):
    """Schema for bulk re-analyze response"""

    queued: int
    skipped: int  # Already processing
    failed: list[str] = []


# Unread Reader schemas
class UnreadNavigationResponse(BaseModel):
    """Schema for unread article navigation"""

    current_position: int
    total_unread: int
    prev_id: UUID | None
    next_id: UUID | None


class UnreadListResponse(BaseModel):
    """Schema for list of unread article IDs"""

    items: list[UUID]
    total: int


# Update forward references
ArticleResponse.model_rebuild()
