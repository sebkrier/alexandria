import uuid
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    articles: Mapped[list["Article"]] = relationship(back_populates="user")
    categories: Mapped[list["Category"]] = relationship(back_populates="user")
    tags: Mapped[list["Tag"]] = relationship(back_populates="user")
    ai_providers: Mapped[list["AIProvider"]] = relationship(back_populates="user")
    colors: Mapped[list["Color"]] = relationship(back_populates="user")
