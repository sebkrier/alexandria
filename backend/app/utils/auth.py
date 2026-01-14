from fastapi import Depends
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.models.color import Color

# Default categories to bootstrap
DEFAULT_CATEGORIES = [
    {"name": "AI & Machine Learning", "children": ["Safety", "Capabilities", "Governance/Policy"]},
    {"name": "Economics", "children": []},
    {"name": "Philosophy", "children": []},
    {"name": "Policy & Regulation", "children": []},
    {"name": "Technical/Engineering", "children": []},
]

# Default colors
DEFAULT_COLORS = [
    {"name": "Unread", "hex_value": "#6B7FD7"},
    {"name": "Important", "hex_value": "#5BA37C"},
    {"name": "To Revisit", "hex_value": "#D4915D"},
    {"name": "Interesting", "hex_value": "#9B7FC7"},
    {"name": "Urgent", "hex_value": "#D46A6A"},
    {"name": "Archived", "hex_value": "#6B7280"},
]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get or create the default user (no authentication required)"""
    # Get the first user, or create a default one
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()

    if not user:
        # Create default user
        user = User(
            email="default@alexandria.local",
            password_hash=hash_password("not-used"),
        )
        db.add(user)
        await db.flush()

        # Bootstrap default categories
        for position, cat_data in enumerate(DEFAULT_CATEGORIES):
            parent = Category(
                user_id=user.id,
                name=cat_data["name"],
                position=position,
            )
            db.add(parent)
            await db.flush()

            for child_pos, child_name in enumerate(cat_data["children"]):
                child = Category(
                    user_id=user.id,
                    name=child_name,
                    parent_id=parent.id,
                    position=child_pos,
                )
                db.add(child)

        # Bootstrap default colors
        for position, color_data in enumerate(DEFAULT_COLORS):
            color = Color(
                user_id=user.id,
                name=color_data["name"],
                hex_value=color_data["hex_value"],
                position=position,
            )
            db.add(color)

        await db.commit()
        await db.refresh(user)

    return user
