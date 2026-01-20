from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ai_provider import AIProvider as AIProviderModel
from app.models.ai_provider import ProviderName
from app.models.article import Article
from app.models.color import Color
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.encryption import decrypt_api_key, encrypt_api_key, mask_api_key

from .utils import fetch_colors, fetch_sidebar_data, templates

router = APIRouter()

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Settings page with AI providers and colors."""
    from app.ai.factory import get_available_providers
    from app.ai.prompts import (
        SUMMARY_SYSTEM_PROMPT,
        EXTRACT_SUMMARY_PROMPT,
        TAGS_SYSTEM_PROMPT,
        TAGS_USER_PROMPT,
        CATEGORY_SYSTEM_PROMPT,
        CATEGORY_USER_PROMPT,
        QUESTION_SYSTEM_PROMPT,
        QUESTION_USER_PROMPT,
    )

    # Fetch providers
    result = await db.execute(
        select(AIProviderModel)
        .where(AIProviderModel.user_id == current_user.id)
        .order_by(AIProviderModel.created_at)
    )
    provider_models = result.scalars().all()

    providers = []
    for p in provider_models:
        api_key = decrypt_api_key(p.api_key_encrypted)
        providers.append(
            {
                "id": str(p.id),
                "provider_name": p.provider_name.value
                if hasattr(p.provider_name, "value")
                else str(p.provider_name),
                "display_name": p.display_name,
                "model_id": p.model_id,
                "api_key_masked": mask_api_key(api_key),
                "is_default": p.is_default,
                "is_active": p.is_active,
            }
        )

    # Fetch colors
    colors = await fetch_colors(db, current_user.id)

    # Fetch sidebar data
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    # Get available providers info
    available_providers = get_available_providers()

    # Get prompts - organized by function
    prompts = {
        "summarization": {
            "name": "Article Summarization",
            "description": "Generates detailed summaries of saved articles",
            "system": SUMMARY_SYSTEM_PROMPT,
            "user": EXTRACT_SUMMARY_PROMPT,
        },
        "tagging": {
            "name": "Tag Suggestion",
            "description": "Suggests relevant tags for categorizing articles",
            "system": TAGS_SYSTEM_PROMPT,
            "user": TAGS_USER_PROMPT,
        },
        "categorization": {
            "name": "Category Assignment",
            "description": "Assigns articles to categories and subcategories",
            "system": CATEGORY_SYSTEM_PROMPT,
            "user": CATEGORY_USER_PROMPT,
        },
        "questioning": {
            "name": "Ask Questions",
            "description": "Answers questions based on your library content",
            "system": QUESTION_SYSTEM_PROMPT,
            "user": QUESTION_USER_PROMPT,
        },
    }

    return templates.TemplateResponse(
        request=request,
        name="pages/settings.html",
        context={
            "providers": providers,
            "available_providers": available_providers,
            "colors": colors,
            "prompts": prompts,
            "current_path": "/app/settings",
            **sidebar_data,
        },
    )

@router.get("/modals/add-provider", response_class=HTMLResponse)
async def add_provider_modal(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the add provider modal HTML."""
    from app.ai.factory import get_available_providers

    available_providers = get_available_providers()

    return templates.TemplateResponse(
        request=request,
        name="modals/add_provider.html",
        context={
            "available_providers": available_providers,
        },
    )


@router.post("/settings/providers", response_class=HTMLResponse)
async def create_provider(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new AI provider."""
    form = await request.form()
    provider_name = form.get("provider_name")
    display_name = form.get("display_name")
    model_id = form.get("model_id")
    api_key = form.get("api_key")

    # Check if this is the first provider
    result = await db.execute(
        select(AIProviderModel).where(AIProviderModel.user_id == current_user.id).limit(1)
    )
    is_first = result.scalar_one_or_none() is None

    # Encrypt API key
    encrypted_key = encrypt_api_key(api_key)

    provider = AIProviderModel(
        user_id=current_user.id,
        provider_name=ProviderName(provider_name),
        display_name=display_name,
        model_id=model_id,
        api_key_encrypted=encrypted_key,
        is_default=is_first,
        is_active=True,
    )

    db.add(provider)
    await db.commit()

    # Return updated providers list
    return await _render_providers_list(request, db, current_user.id)


@router.post("/settings/providers/{provider_id}/test", response_class=HTMLResponse)
async def test_provider(
    request: Request,
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test an AI provider connection."""
    from app.ai.factory import get_ai_provider

    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider_config = result.scalar_one_or_none()

    if not provider_config:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Provider not found",
            },
        )

    try:
        provider = await get_ai_provider(db, provider_id)
        success = await provider.health_check()

        if success:
            return templates.TemplateResponse(
                request=request,
                name="components/toast.html",
                context={
                    "toast_type": "success",
                    "toast_message": f"Successfully connected to {provider_config.display_name}",
                },
            )
        else:
            return templates.TemplateResponse(
                request=request,
                name="components/toast.html",
                context={
                    "toast_type": "error",
                    "toast_message": "Connection failed - please check your API key",
                },
            )
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": f"Error: {str(e)}",
            },
        )


@router.post("/settings/providers/{provider_id}/default", response_class=HTMLResponse)
async def set_default_provider(
    request: Request,
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a provider as default."""
    # Unset all defaults
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.user_id == current_user.id,
            AIProviderModel.is_default == True,  # noqa: E712
        )
    )
    for p in result.scalars().all():
        p.is_default = False

    # Set new default
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()
    if provider:
        provider.is_default = True

    await db.commit()

    # Return updated providers list
    return await _render_providers_list(request, db, current_user.id)


@router.delete("/settings/providers/{provider_id}", response_class=HTMLResponse)
async def delete_provider(
    request: Request,
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an AI provider."""
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()

    if provider:
        was_default = provider.is_default
        await db.delete(provider)
        await db.commit()

        # If deleted provider was default, make another one default
        if was_default:
            result = await db.execute(
                select(AIProviderModel).where(AIProviderModel.user_id == current_user.id).limit(1)
            )
            new_default = result.scalar_one_or_none()
            if new_default:
                new_default.is_default = True
                await db.commit()

    # Return empty string to remove the element
    return ""


async def _render_providers_list(request: Request, db: AsyncSession, user_id: UUID) -> HTMLResponse:
    """Helper to render the providers list partial."""
    result = await db.execute(
        select(AIProviderModel)
        .where(AIProviderModel.user_id == user_id)
        .order_by(AIProviderModel.created_at)
    )
    provider_models = result.scalars().all()

    providers = []
    for p in provider_models:
        api_key = decrypt_api_key(p.api_key_encrypted)
        providers.append(
            {
                "id": str(p.id),
                "provider_name": p.provider_name.value
                if hasattr(p.provider_name, "value")
                else str(p.provider_name),
                "display_name": p.display_name,
                "model_id": p.model_id,
                "api_key_masked": mask_api_key(api_key),
                "is_default": p.is_default,
                "is_active": p.is_active,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_providers_list.html",
        context={"providers": providers},
    )


@router.patch("/settings/colors/{color_id}", response_class=HTMLResponse)
async def update_color(
    request: Request,
    color_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a color label name."""
    form = await request.form()
    name = form.get("name")

    result = await db.execute(
        select(Color).where(
            Color.id == color_id,
            Color.user_id == current_user.id,
        )
    )
    color = result.scalar_one_or_none()

    if color and name:
        color.name = name
        await db.commit()
        await db.refresh(color)

    # Fetch all colors and return the full section (includes OOB swap for sidebar)
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_colors.html",
        context={"colors": colors},
    )


@router.post("/settings/colors", response_class=HTMLResponse)
async def create_color(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new color label."""
    form = await request.form()
    name = form.get("name", "New Color")
    hex_value = form.get("hex_value", "#808080")

    # Get the max position for ordering
    result = await db.execute(
        select(func.max(Color.position)).where(Color.user_id == current_user.id)
    )
    max_position = result.scalar() or 0

    # Create new color
    color = Color(
        user_id=current_user.id,
        name=name,
        hex_value=hex_value,
        position=max_position + 1,
    )
    db.add(color)
    await db.commit()
    await db.refresh(color)

    # Fetch all colors and return the full section
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_colors.html",
        context={"colors": colors},
    )


@router.delete("/settings/colors/{color_id}", response_class=HTMLResponse)
async def delete_color(
    request: Request,
    color_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a color label. Articles with this color will have their color cleared."""
    # Find the color
    result = await db.execute(
        select(Color).where(
            Color.id == color_id,
            Color.user_id == current_user.id,
        )
    )
    color = result.scalar_one_or_none()

    if not color:
        return HTMLResponse("<div>Color not found</div>", status_code=404)

    # Clear color from articles that use it
    await db.execute(
        Article.__table__.update().where(Article.color_id == color_id).values(color_id=None)
    )

    # Delete the color
    await db.delete(color)
    await db.commit()

    # Fetch remaining colors and return the full section
    colors = await fetch_colors(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_colors.html",
        context={"colors": colors},
    )
