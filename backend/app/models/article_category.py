import uuid
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


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
    article: Mapped["Article"] = relationship(back_populates="categories")
    category: Mapped["Category"] = relationship(back_populates="articles")
