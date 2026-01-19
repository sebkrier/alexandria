"""
Tests for the AI provider factory (app/ai/factory.py).

Tests provider instantiation, default provider selection, and error handling
for unsupported or inactive providers.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.factory import (
    PROVIDER_DISPLAY_NAMES,
    SUPPORTED_PROVIDERS,
    _instantiate_provider,
    get_ai_provider,
    get_all_providers,
    get_available_providers,
    get_default_provider,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_provider_config():
    """Factory for creating mock AIProviderModel objects."""

    def _create(
        provider_name: str = "anthropic",
        model_id: str = "claude-sonnet-4-20250514",
        display_name: str = "Test Provider",
        is_active: bool = True,
        is_default: bool = False,
        api_key_encrypted: str = "encrypted_key_123",
        provider_id=None,
        user_id=None,
    ):
        config = MagicMock()
        config.id = provider_id or uuid4()
        config.user_id = user_id or uuid4()
        config.provider_name = provider_name
        config.model_id = model_id
        config.display_name = display_name
        config.is_active = is_active
        config.is_default = is_default
        config.api_key_encrypted = api_key_encrypted
        return config

    return _create


# =============================================================================
# get_ai_provider() Tests
# =============================================================================


class TestGetAIProvider:
    """Tests for fetching AI provider by ID."""

    @pytest.mark.asyncio
    async def test_get_provider_by_id(
        self, async_db_session, test_user, test_ai_provider
    ):
        """Test fetching an existing provider by ID."""
        with patch("app.ai.factory.decrypt_api_key", return_value="decrypted_key"):
            provider = await get_ai_provider(async_db_session, test_ai_provider.id)

            assert provider is not None

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, async_db_session):
        """Test error when provider ID doesn't exist."""
        non_existent_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            await get_ai_provider(async_db_session, non_existent_id)

    @pytest.mark.asyncio
    async def test_get_inactive_provider_raises_error(
        self, async_db_session, test_user
    ):
        """Test error when trying to use an inactive provider."""
        from app.models.ai_provider import AIProvider, ProviderName
        from app.utils.encryption import encrypt_api_key

        # Create inactive provider
        inactive_provider = AIProvider(
            user_id=test_user.id,
            provider_name=ProviderName.ANTHROPIC,
            display_name="Inactive Provider",
            model_id="claude-sonnet-4-20250514",
            api_key_encrypted=encrypt_api_key("test-key"),
            is_default=False,
            is_active=False,
        )
        async_db_session.add(inactive_provider)
        await async_db_session.commit()
        await async_db_session.refresh(inactive_provider)

        with pytest.raises(ValueError, match="is disabled"):
            await get_ai_provider(async_db_session, inactive_provider.id)


# =============================================================================
# get_default_provider() Tests
# =============================================================================


class TestGetDefaultProvider:
    """Tests for fetching user's default AI provider."""

    @pytest.mark.asyncio
    async def test_get_default_provider(
        self, async_db_session, test_user, test_ai_provider
    ):
        """Test fetching the default provider."""
        with patch("app.ai.factory.decrypt_api_key", return_value="decrypted_key"):
            provider = await get_default_provider(async_db_session, test_user.id)

            assert provider is not None

    @pytest.mark.asyncio
    async def test_get_default_provider_falls_back_to_active(
        self, async_db_session, test_user
    ):
        """Test fallback to any active provider when no default set."""
        from app.models.ai_provider import AIProvider, ProviderName
        from app.utils.encryption import encrypt_api_key

        # Create a non-default but active provider
        active_provider = AIProvider(
            user_id=test_user.id,
            provider_name=ProviderName.OPENAI,
            display_name="Active OpenAI",
            model_id="gpt-5.2",
            api_key_encrypted=encrypt_api_key("test-key"),
            is_default=False,
            is_active=True,
        )
        async_db_session.add(active_provider)
        await async_db_session.commit()

        with patch("app.ai.factory.decrypt_api_key", return_value="decrypted_key"):
            provider = await get_default_provider(async_db_session, test_user.id)

            assert provider is not None

    @pytest.mark.asyncio
    async def test_get_default_provider_no_providers(self, async_db_session, test_user):
        """Test returns None when user has no providers."""
        # test_user has no providers by default (unless test_ai_provider fixture is used)
        provider = await get_default_provider(async_db_session, test_user.id)

        assert provider is None


# =============================================================================
# get_all_providers() Tests
# =============================================================================


class TestGetAllProviders:
    """Tests for fetching all user providers."""

    @pytest.mark.asyncio
    async def test_get_all_providers(
        self, async_db_session, test_user, test_ai_provider
    ):
        """Test fetching all providers for a user."""
        with patch("app.ai.factory.decrypt_api_key", return_value="decrypted_key"):
            providers = await get_all_providers(async_db_session, test_user.id)

            assert len(providers) >= 1
            # Each item is (config, instance) tuple
            assert len(providers[0]) == 2

    @pytest.mark.asyncio
    async def test_get_all_providers_active_only(
        self, async_db_session, test_user
    ):
        """Test filtering to only active providers."""
        from app.models.ai_provider import AIProvider, ProviderName
        from app.utils.encryption import encrypt_api_key

        # Create one active and one inactive provider
        active = AIProvider(
            user_id=test_user.id,
            provider_name=ProviderName.ANTHROPIC,
            display_name="Active",
            model_id="claude-sonnet-4-20250514",
            api_key_encrypted=encrypt_api_key("key1"),
            is_active=True,
        )
        inactive = AIProvider(
            user_id=test_user.id,
            provider_name=ProviderName.OPENAI,
            display_name="Inactive",
            model_id="gpt-5.2",
            api_key_encrypted=encrypt_api_key("key2"),
            is_active=False,
        )
        async_db_session.add(active)
        async_db_session.add(inactive)
        await async_db_session.commit()

        with patch("app.ai.factory.decrypt_api_key", return_value="decrypted_key"):
            providers = await get_all_providers(
                async_db_session, test_user.id, active_only=True
            )

            # Should only include active provider
            display_names = [config.display_name for config, _ in providers]
            assert "Active" in display_names
            assert "Inactive" not in display_names


# =============================================================================
# _instantiate_provider() Tests
# =============================================================================


class TestInstantiateProvider:
    """Tests for provider instantiation logic."""

    def test_instantiate_anthropic_provider(self, mock_provider_config):
        """Test instantiating Anthropic provider."""
        config = mock_provider_config(provider_name="anthropic")

        with patch("app.ai.factory.decrypt_api_key", return_value="sk-ant-test"):
            provider = _instantiate_provider(config)

            assert provider is not None

    def test_instantiate_openai_provider(self, mock_provider_config):
        """Test instantiating OpenAI provider."""
        config = mock_provider_config(provider_name="openai", model_id="gpt-5.2")

        with patch("app.ai.factory.decrypt_api_key", return_value="sk-openai-test"):
            provider = _instantiate_provider(config)

            assert provider is not None

    def test_instantiate_google_provider(self, mock_provider_config):
        """Test instantiating Google provider."""
        config = mock_provider_config(provider_name="google", model_id="gemini-3.0-pro")

        with patch("app.ai.factory.decrypt_api_key", return_value="google-api-key"):
            provider = _instantiate_provider(config)

            assert provider is not None

    def test_instantiate_unsupported_provider_raises(self, mock_provider_config):
        """Test error for unsupported provider type."""
        config = mock_provider_config(provider_name="unsupported_provider")

        with patch("app.ai.factory.decrypt_api_key", return_value="key"):
            with pytest.raises(ValueError, match="Unsupported provider"):
                _instantiate_provider(config)

    def test_instantiate_handles_enum_provider_name(self, mock_provider_config):
        """Test handling provider_name as enum value."""
        # Simulate an enum-like object
        mock_enum = MagicMock()
        mock_enum.value = "anthropic"
        config = mock_provider_config()
        config.provider_name = mock_enum

        with patch("app.ai.factory.decrypt_api_key", return_value="key"):
            provider = _instantiate_provider(config)

            assert provider is not None


# =============================================================================
# get_available_providers() Tests
# =============================================================================


class TestGetAvailableProviders:
    """Tests for available providers info."""

    def test_returns_all_providers(self):
        """Test that all supported providers are returned."""
        providers = get_available_providers()

        assert "anthropic" in providers
        assert "openai" in providers
        assert "google" in providers

    def test_provider_has_display_name(self):
        """Test each provider has a display name."""
        providers = get_available_providers()

        for _provider_name, info in providers.items():
            assert "display_name" in info
            assert len(info["display_name"]) > 0

    def test_provider_has_models(self):
        """Test each provider has available models."""
        providers = get_available_providers()

        for _provider_name, info in providers.items():
            assert "models" in info
            assert len(info["models"]) > 0

    def test_provider_has_default_model(self):
        """Test each provider has a default model."""
        providers = get_available_providers()

        for _provider_name, info in providers.items():
            assert "default_model" in info
            assert info["default_model"] in info["models"]


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for factory constants."""

    def test_supported_providers_includes_major_providers(self):
        """Test that major AI providers are supported."""
        assert "anthropic" in SUPPORTED_PROVIDERS
        assert "openai" in SUPPORTED_PROVIDERS
        assert "google" in SUPPORTED_PROVIDERS

    def test_display_names_for_all_supported(self):
        """Test display names exist for all supported providers."""
        for provider in SUPPORTED_PROVIDERS:
            assert provider in PROVIDER_DISPLAY_NAMES
