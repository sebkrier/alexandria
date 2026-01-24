from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article_tag import ArticleTag
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """List all tags"""
    result = await db.execute(select(Tag).where(Tag.user_id == current_user.id).order_by(Tag.name))
    tags = result.scalars().all()

    response = []
    for tag in tags:
        # Get article count
        count_result = await db.execute(
            select(func.count(ArticleTag.article_id)).where(ArticleTag.tag_id == tag.id)
        )
        article_count = count_result.scalar()

        response.append(
            TagResponse(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                article_count=article_count,
                created_at=tag.created_at,
            )
        )

    return response


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TagResponse:
    """Create a new tag"""
    # Check if tag with same name exists
    result = await db.execute(
        select(Tag).where(Tag.user_id == current_user.id, Tag.name == data.name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists",
        )

    tag = Tag(
        user_id=current_user.id,
        name=data.name,
        color=data.color,
    )

    db.add(tag)
    await db.commit()
    await db.refresh(tag)

    return TagResponse(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        article_count=0,
        created_at=tag.created_at,
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a tag"""
    result = await db.execute(select(Tag).where(Tag.id == tag_id, Tag.user_id == current_user.id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await db.delete(tag)
    await db.commit()
