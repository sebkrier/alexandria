import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from app.database import Base


class SourceType(str, Enum):
    URL = "url"
    PDF = "pdf"
    ARXIV = "arxiv"
    VIDEO = "video"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    source_type: Mapped[SourceType] = mapped_column(String(20))
    original_url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[dict | None] = mapped_column(JSONB, default=list)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime)
    extracted_text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_model: Mapped[str | None] = mapped_column(String(100))
    color_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("colors.id")
    )
    file_path: Mapped[str | None] = mapped_column(String(500))
    article_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        String(20), default=ProcessingStatus.PENDING
    )
    processing_error: Mapped[str | None] = mapped_column(Text)

    # Full-text search vector
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="articles")
    color: Mapped["Color"] = relationship(back_populates="articles")
    categories: Mapped[list["ArticleCategory"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    tags: Mapped[list["ArticleTag"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_articles_search_vector", "search_vector", postgresql_using="gin"),
    )
