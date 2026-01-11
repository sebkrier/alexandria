from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class CategoryCreate(BaseModel):
    """Schema for creating a category"""
    name: str
    parent_id: UUID | None = None
    description: str | None = None


class CategoryUpdate(BaseModel):
    """Schema for updating a category"""
    name: str | None = None
    parent_id: UUID | None = None
    description: str | None = None
    position: int | None = None


class CategoryResponse(BaseModel):
    """Schema for category responses"""
    id: UUID
    name: str
    parent_id: UUID | None
    description: str | None
    position: int
    article_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryTree(BaseModel):
    """Schema for hierarchical category tree"""
    id: UUID
    name: str
    description: str | None
    position: int
    article_count: int = 0
    children: list["CategoryTree"] = []

    class Config:
        from_attributes = True


# Update forward references
CategoryTree.model_rebuild()
