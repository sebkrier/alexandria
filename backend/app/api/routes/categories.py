from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article_category import ArticleCategory
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryTree, CategoryUpdate
from app.utils.auth import get_current_user

router = APIRouter()


async def build_category_tree(
    db: AsyncSession, user_id: UUID, parent_id: UUID | None = None
) -> list[CategoryTree]:
    """Recursively build category tree with cumulative article counts"""
    result = await db.execute(
        select(Category)
        .where(Category.user_id == user_id, Category.parent_id == parent_id)
        .order_by(Category.position)
    )
    categories = result.scalars().all()

    tree = []
    for cat in categories:
        # Get direct article count for this category
        count_result = await db.execute(
            select(func.count(ArticleCategory.article_id)).where(
                ArticleCategory.category_id == cat.id
            )
        )
        direct_count = count_result.scalar() or 0

        # Get children recursively
        children = await build_category_tree(db, user_id, cat.id)

        # For parent categories, show cumulative count (sum of children's articles)
        # This makes sense since articles are assigned to subcategories, not parents
        cumulative_count = direct_count + sum(child.article_count for child in children)

        tree.append(
            CategoryTree(
                id=cat.id,
                name=cat.name,
                description=cat.description,
                position=cat.position,
                article_count=cumulative_count,
                children=children,
            )
        )

    return tree


@router.get("", response_model=list[CategoryTree])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get category tree"""
    return await build_category_tree(db, current_user.id)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new category"""
    # Get max position for ordering
    result = await db.execute(
        select(func.max(Category.position)).where(
            Category.user_id == current_user.id, Category.parent_id == data.parent_id
        )
    )
    max_position = result.scalar() or 0

    category = Category(
        user_id=current_user.id,
        name=data.name,
        parent_id=data.parent_id,
        description=data.description,
        position=max_position + 1,
    )

    db.add(category)
    await db.commit()
    await db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
        position=category.position,
        article_count=0,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a category"""
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == current_user.id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    if data.name is not None:
        category.name = data.name
    if data.parent_id is not None:
        category.parent_id = data.parent_id
    if data.description is not None:
        category.description = data.description
    if data.position is not None:
        category.position = data.position

    await db.commit()
    await db.refresh(category)

    # Get article count
    count_result = await db.execute(
        select(func.count(ArticleCategory.article_id)).where(
            ArticleCategory.category_id == category.id
        )
    )
    article_count = count_result.scalar()

    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
        position=category.position,
        article_count=article_count,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a category"""
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == current_user.id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Move children to parent (or make them root)
    children_result = await db.execute(
        select(Category).where(Category.parent_id == category_id)
    )
    for child in children_result.scalars().all():
        child.parent_id = category.parent_id

    await db.delete(category)
    await db.commit()
