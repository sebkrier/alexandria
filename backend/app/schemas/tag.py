from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TagCreate(BaseModel):
    """Schema for creating a tag"""

    name: str
    color: str | None = None


class TagResponse(BaseModel):
    """Schema for tag responses"""

    id: UUID
    name: str
    color: str | None
    article_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True
