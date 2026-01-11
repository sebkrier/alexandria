import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class SuggestionType(str, Enum):
    NEW_CATEGORY = "new_category"
    MERGE = "merge"
    SPLIT = "split"
    MOVE = "move"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class ReorganizationSuggestion(Base):
    __tablename__ = "reorganization_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    suggestion_type: Mapped[SuggestionType] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    affected_articles: Mapped[dict] = mapped_column(JSONB, default=list)
    suggested_action: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[SuggestionStatus] = mapped_column(
        String(20), default=SuggestionStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship()
