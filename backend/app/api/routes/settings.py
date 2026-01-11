from uuid import UUID
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.ai_provider import AIProvider as AIProviderModel, ProviderName
from app.models.color import Color
from app.schemas.ai_provider import (
    AIProviderCreate,
    AIProviderUpdate,
    AIProviderResponse,
    AIProviderTestResult,
    AvailableProvidersResponse,
)
from app.utils.auth import get_current_user
from app.utils.encryption import encrypt_api_key, decrypt_api_key, mask_api_key
from app.ai.factory import get_ai_provider, get_available_providers
from app.ai.prompts import SUMMARY_SYSTEM_PROMPT, EXTRACT_SUMMARY_PROMPT

router = APIRouter()


class PromptResponse(BaseModel):
    system_prompt: str
    user_prompt: str


class PromptUpdate(BaseModel):
    system_prompt: str | None = None
    user_prompt: str | None = None


def provider_to_response(provider: AIProviderModel) -> AIProviderResponse:
    """Convert provider model to response with masked API key"""
    api_key = decrypt_api_key(provider.api_key_encrypted)
    return AIProviderResponse(
        id=provider.id,
        provider_name=provider.provider_name,
        display_name=provider.display_name,
        model_id=provider.model_id,
        api_key_masked=mask_api_key(api_key),
        is_default=provider.is_default,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.get("/providers/available", response_model=AvailableProvidersResponse)
async def get_available_ai_providers():
    """Get information about available AI providers and their models"""
    return AvailableProvidersResponse(providers=get_available_providers())


@router.get("/providers", response_model=list[AIProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all configured AI providers"""
    result = await db.execute(
        select(AIProviderModel)
        .where(AIProviderModel.user_id == current_user.id)
        .order_by(AIProviderModel.created_at)
    )
    providers = result.scalars().all()

    return [provider_to_response(p) for p in providers]


@router.post("/providers", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: AIProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new AI provider configuration"""
    # Check if this is the first provider (make it default)
    result = await db.execute(
        select(AIProviderModel).where(AIProviderModel.user_id == current_user.id).limit(1)
    )
    is_first = result.scalar_one_or_none() is None

    # Encrypt the API key
    encrypted_key = encrypt_api_key(data.api_key)

    provider = AIProviderModel(
        user_id=current_user.id,
        provider_name=data.provider_name,
        display_name=data.display_name,
        model_id=data.model_id,
        api_key_encrypted=encrypted_key,
        is_default=is_first,
        is_active=True,
    )

    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    return provider_to_response(provider)


@router.get("/providers/{provider_id}", response_model=AIProviderResponse)
async def get_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single AI provider configuration"""
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )

    return provider_to_response(provider)


@router.patch("/providers/{provider_id}", response_model=AIProviderResponse)
async def update_provider(
    provider_id: UUID,
    data: AIProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an AI provider configuration"""
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )

    if data.display_name is not None:
        provider.display_name = data.display_name
    if data.model_id is not None:
        provider.model_id = data.model_id
    if data.api_key is not None:
        provider.api_key_encrypted = encrypt_api_key(data.api_key)
    if data.is_active is not None:
        provider.is_active = data.is_active

    # Handle default flag - ensure only one default
    if data.is_default is True:
        # Unset other defaults
        await db.execute(
            select(AIProviderModel)
            .where(
                AIProviderModel.user_id == current_user.id,
                AIProviderModel.is_default == True,
            )
        )
        result = await db.execute(
            select(AIProviderModel).where(
                AIProviderModel.user_id == current_user.id,
                AIProviderModel.is_default == True,
            )
        )
        for p in result.scalars().all():
            p.is_default = False

        provider.is_default = True

    await db.commit()
    await db.refresh(provider)

    return provider_to_response(provider)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an AI provider configuration"""
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )

    was_default = provider.is_default

    await db.delete(provider)
    await db.commit()

    # If deleted provider was default, make another one default
    if was_default:
        result = await db.execute(
            select(AIProviderModel)
            .where(AIProviderModel.user_id == current_user.id)
            .limit(1)
        )
        new_default = result.scalar_one_or_none()
        if new_default:
            new_default.is_default = True
            await db.commit()


@router.post("/providers/{provider_id}/test", response_model=AIProviderTestResult)
async def test_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test an AI provider configuration"""
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.id == provider_id,
            AIProviderModel.user_id == current_user.id,
        )
    )
    provider_config = result.scalar_one_or_none()

    if not provider_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )

    try:
        provider = await get_ai_provider(db, provider_id)
        success = await provider.health_check()

        if success:
            return AIProviderTestResult(
                success=True,
                message=f"Successfully connected to {provider_config.display_name}",
            )
        else:
            return AIProviderTestResult(
                success=False,
                message="Connection failed - please check your API key",
            )
    except Exception as e:
        return AIProviderTestResult(
            success=False,
            message=f"Error: {str(e)}",
        )


# Color settings endpoints

@router.get("/colors")
async def list_colors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all color configurations"""
    result = await db.execute(
        select(Color)
        .where(Color.user_id == current_user.id)
        .order_by(Color.position)
    )
    colors = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "hex_value": c.hex_value,
            "position": c.position,
        }
        for c in colors
    ]


@router.patch("/colors/{color_id}")
async def update_color(
    color_id: UUID,
    name: str | None = None,
    hex_value: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a color configuration"""
    result = await db.execute(
        select(Color).where(
            Color.id == color_id,
            Color.user_id == current_user.id,
        )
    )
    color = result.scalar_one_or_none()

    if not color:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Color not found",
        )

    if name is not None:
        color.name = name
    if hex_value is not None:
        color.hex_value = hex_value

    await db.commit()
    await db.refresh(color)

    return {
        "id": color.id,
        "name": color.name,
        "hex_value": color.hex_value,
        "position": color.position,
    }


# Prompt settings endpoints

@router.get("/prompts/summary", response_model=PromptResponse)
async def get_summary_prompt(
    current_user: User = Depends(get_current_user),
):
    """Get the current summarization prompt"""
    return PromptResponse(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=EXTRACT_SUMMARY_PROMPT,
    )
