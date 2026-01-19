"""
Factory for creating AI provider instances from database configuration.
Uses LiteLLM for unified provider interface.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider
from app.ai.llm import PROVIDER_MODELS, LiteLLMProvider
from app.models.ai_provider import AIProvider as AIProviderModel
from app.utils.encryption import decrypt_api_key

logger = logging.getLogger(__name__)

# Supported providers (LiteLLM handles all of them)
SUPPORTED_PROVIDERS = {"anthropic", "openai", "google"}


async def get_ai_provider(
    db: AsyncSession,
    provider_id: UUID,
) -> AIProvider:
    """
    Get an AI provider instance by its database ID.

    Args:
        db: Database session
        provider_id: UUID of the provider configuration

    Returns:
        Instantiated AIProvider

    Raises:
        ValueError: If provider not found or not supported
    """
    result = await db.execute(select(AIProviderModel).where(AIProviderModel.id == provider_id))
    provider_config = result.scalar_one_or_none()

    if not provider_config:
        raise ValueError(f"AI provider {provider_id} not found")

    if not provider_config.is_active:
        raise ValueError(f"AI provider {provider_config.display_name} is disabled")

    return _instantiate_provider(provider_config)


async def get_default_provider(
    db: AsyncSession,
    user_id: UUID,
) -> AIProvider | None:
    """
    Get the user's default AI provider.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        Instantiated AIProvider or None if no default configured
    """
    result = await db.execute(
        select(AIProviderModel).where(
            AIProviderModel.user_id == user_id,
            AIProviderModel.is_default.is_(True),
            AIProviderModel.is_active.is_(True),
        )
    )
    provider_config = result.scalar_one_or_none()

    if not provider_config:
        # Fall back to any active provider
        result = await db.execute(
            select(AIProviderModel)
            .where(
                AIProviderModel.user_id == user_id,
                AIProviderModel.is_active.is_(True),
            )
            .limit(1)
        )
        provider_config = result.scalar_one_or_none()

    if not provider_config:
        return None

    return _instantiate_provider(provider_config)


async def get_all_providers(
    db: AsyncSession,
    user_id: UUID,
    active_only: bool = True,
) -> list[tuple[AIProviderModel, AIProvider]]:
    """
    Get all configured providers for a user.

    Returns list of (config, instance) tuples.
    """
    query = select(AIProviderModel).where(AIProviderModel.user_id == user_id)
    if active_only:
        query = query.where(AIProviderModel.is_active.is_(True))

    result = await db.execute(query)
    configs = result.scalars().all()

    providers = []
    for config in configs:
        try:
            instance = _instantiate_provider(config)
            providers.append((config, instance))
        except Exception as e:
            logger.warning(f"Failed to instantiate provider {config.display_name}: {e}")

    return providers


def _instantiate_provider(config: AIProviderModel) -> AIProvider:
    """Create an AI provider instance from database configuration using LiteLLM."""
    # Handle both enum and string values from database
    provider_key = (
        config.provider_name.value
        if hasattr(config.provider_name, "value")
        else str(config.provider_name)
    )

    if provider_key not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider_key}")

    # Decrypt the API key
    api_key = decrypt_api_key(config.api_key_encrypted)

    # Use LiteLLMProvider for all providers
    return LiteLLMProvider(
        api_key=api_key,
        model_id=config.model_id,
        provider_name=provider_key,
    )


# Proper display names for providers
PROVIDER_DISPLAY_NAMES = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
}


def get_available_providers() -> dict:
    """
    Get information about all available AI providers and their models.
    Used by the settings UI.
    """
    return {
        provider_name: {
            "display_name": PROVIDER_DISPLAY_NAMES.get(provider_name, provider_name.title()),
            "models": models,
            "default_model": list(models.keys())[0],
        }
        for provider_name, models in PROVIDER_MODELS.items()
    }
