import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Color(Base):
    __tablename__ = "colors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))  # e.g., "Important", "To Revisit"
    hex_value: Mapped[str] = mapped_column(String(7))  # e.g., "#6B7FD7"
    position: Mapped[int] = mapped_column(Integer, default=0)  # For ordering
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="colors")
    articles: Mapped[list["Article"]] = relationship(back_populates="color")
