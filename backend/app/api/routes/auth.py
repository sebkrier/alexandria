from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.models.color import Color
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.utils.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()

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


@router.post("/setup", response_model=UserResponse)
async def setup(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Initial setup endpoint - creates the first user if none exists.
    Only works when no users exist in the database.
    """
    # Check if any users exist
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup already completed. Use /login instead.",
        )

    # Create user
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )
    db.add(user)
    await db.flush()  # Get user ID

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


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token"""
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id)

    # Set cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return Token(access_token=token)


@router.post("/logout")
async def logout(response: Response):
    """Logout and clear access token cookie"""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user


@router.get("/check-setup")
async def check_setup(db: AsyncSession = Depends(get_db)):
    """Check if initial setup has been completed"""
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()

    return {"setup_required": user_count == 0}
