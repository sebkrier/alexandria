import uuid
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ArticleTag(Base):
    __tablename__ = "article_tags"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True
    )
    suggested_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship(back_populates="articles")
