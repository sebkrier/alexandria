from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.category import Category


class ArticleCategory(Base):
    __tablename__ = "article_categories"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    article: Mapped[Article] = relationship(back_populates="categories")
    category: Mapped[Category] = relationship(back_populates="articles")
