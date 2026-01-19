"""
Tests for the settings API endpoints (providers, colors, prompts).

Coverage target: 85%+ of app/api/routes/settings.py
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


class TestAvailableProviders:
    """Tests for GET /api/settings/providers/available endpoint."""

    @pytest.mark.asyncio
    async def test_get_available_providers(self, test_client):
        """Test getting list of available AI providers."""
        response = await test_client.get("/api/settings/providers/available")

        assert response.status_code == 200
        data = response.json()
        assert "providers" in data

        # Should have the major providers
        providers = data["providers"]
        assert "anthropic" in providers
        assert "openai" in providers
        assert "google" in providers

        # Each provider should have models
        for _provider_name, provider_info in providers.items():
            assert "models" in provider_info
            assert len(provider_info["models"]) > 0


class TestListProviders:
    """Tests for GET /api/settings/providers endpoint."""

    @pytest.mark.asyncio
    async def test_list_providers_empty(self, test_client):
        """Test listing providers when none configured."""
        response = await test_client.get("/api/settings/providers")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_providers_with_data(self, test_client, test_ai_provider):
        """Test listing configured providers."""
        response = await test_client.get("/api/settings/providers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["display_name"] == test_ai_provider.display_name
        assert data[0]["model_id"] == test_ai_provider.model_id
        assert data[0]["is_default"] is True
        # API key should be masked (format: "sk-...2345" where 2345 is last 4 chars)
        assert "sk-test-key-12345" not in data[0]["api_key_masked"]
        assert "..." in data[0]["api_key_masked"]


class TestCreateProvider:
    """Tests for POST /api/settings/providers endpoint."""

    @pytest.mark.asyncio
    async def test_create_provider_success(self, test_client):
        """Test creating a new AI provider."""
        response = await test_client.post(
            "/api/settings/providers",
            json={
                "provider_name": "anthropic",
                "display_name": "My Claude",
                "model_id": "claude-sonnet-4-20250514",
                "api_key": "sk-ant-api-key-12345",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "My Claude"
        assert data["model_id"] == "claude-sonnet-4-20250514"
        assert data["provider_name"] == "anthropic"
        # First provider should be default
        assert data["is_default"] is True
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_provider_second_not_default(self, test_client, test_ai_provider):
        """Test second provider is not automatically default."""
        response = await test_client.post(
            "/api/settings/providers",
            json={
                "provider_name": "openai",
                "display_name": "My GPT",
                "model_id": "gpt-5.2",
                "api_key": "sk-openai-key-12345",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_default"] is False  # Second provider not default


class TestGetProvider:
    """Tests for GET /api/settings/providers/{provider_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_provider_success(self, test_client, test_ai_provider):
        """Test getting a single provider."""
        response = await test_client.get(f"/api/settings/providers/{test_ai_provider.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_ai_provider.id)
        assert data["display_name"] == test_ai_provider.display_name

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, test_client):
        """Test getting non-existent provider returns 404."""
        fake_id = uuid4()
        response = await test_client.get(f"/api/settings/providers/{fake_id}")

        assert response.status_code == 404


class TestUpdateProvider:
    """Tests for PATCH /api/settings/providers/{provider_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_provider_display_name(self, test_client, test_ai_provider):
        """Test updating provider display name."""
        response = await test_client.patch(
            f"/api/settings/providers/{test_ai_provider.id}",
            json={"display_name": "Updated Claude"},
        )

        assert response.status_code == 200
        assert response.json()["display_name"] == "Updated Claude"

    @pytest.mark.asyncio
    async def test_update_provider_model(self, test_client, test_ai_provider):
        """Test updating provider model."""
        response = await test_client.patch(
            f"/api/settings/providers/{test_ai_provider.id}",
            json={"model_id": "claude-opus-4-5-20251101"},
        )

        assert response.status_code == 200
        assert response.json()["model_id"] == "claude-opus-4-5-20251101"

    @pytest.mark.asyncio
    async def test_update_provider_api_key(self, test_client, test_ai_provider):
        """Test updating provider API key."""
        response = await test_client.patch(
            f"/api/settings/providers/{test_ai_provider.id}",
            json={"api_key": "sk-new-api-key-67890"},
        )

        assert response.status_code == 200
        # Key should be masked differently
        assert "67890" not in response.json()["api_key_masked"]

    @pytest.mark.asyncio
    async def test_update_provider_set_default(
        self, test_client, test_ai_provider, async_db_session, test_user
    ):
        """Test setting a provider as default unsets others."""
        from app.models.ai_provider import AIProvider, ProviderName
        from app.utils.encryption import encrypt_api_key

        # Create second provider
        second = AIProvider(
            user_id=test_user.id,
            provider_name=ProviderName.OPENAI,
            display_name="GPT Provider",
            model_id="gpt-5.2",
            api_key_encrypted=encrypt_api_key("sk-openai-key"),
            is_default=False,
            is_active=True,
        )
        async_db_session.add(second)
        await async_db_session.commit()

        # Set second as default
        response = await test_client.patch(
            f"/api/settings/providers/{second.id}",
            json={"is_default": True},
        )

        assert response.status_code == 200
        assert response.json()["is_default"] is True

        # Verify first is no longer default
        first_response = await test_client.get(f"/api/settings/providers/{test_ai_provider.id}")
        assert first_response.json()["is_default"] is False

    @pytest.mark.asyncio
    async def test_update_provider_not_found(self, test_client):
        """Test updating non-existent provider returns 404."""
        fake_id = uuid4()
        response = await test_client.patch(
            f"/api/settings/providers/{fake_id}",
            json={"display_name": "Test"},
        )

        assert response.status_code == 404


class TestDeleteProvider:
    """Tests for DELETE /api/settings/providers/{provider_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_provider_success(self, test_client, test_ai_provider):
        """Test deleting a provider."""
        response = await test_client.delete(f"/api/settings/providers/{test_ai_provider.id}")

        assert response.status_code == 204

        # Verify deleted
        list_response = await test_client.get("/api/settings/providers")
        assert list_response.json() == []

    @pytest.mark.asyncio
    async def test_delete_provider_not_found(self, test_client):
        """Test deleting non-existent provider returns 404."""
        fake_id = uuid4()
        response = await test_client.delete(f"/api/settings/providers/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_default_assigns_new_default(
        self, test_client, test_ai_provider, async_db_session, test_user
    ):
        """Test deleting default provider assigns new default."""
        from app.models.ai_provider import AIProvider, ProviderName
        from app.utils.encryption import encrypt_api_key

        # Create second provider
        second = AIProvider(
            user_id=test_user.id,
            provider_name=ProviderName.OPENAI,
            display_name="GPT Provider",
            model_id="gpt-5.2",
            api_key_encrypted=encrypt_api_key("sk-openai-key"),
            is_default=False,
            is_active=True,
        )
        async_db_session.add(second)
        await async_db_session.commit()

        # Delete the default provider
        response = await test_client.delete(f"/api/settings/providers/{test_ai_provider.id}")
        assert response.status_code == 204

        # Check second is now default
        list_response = await test_client.get("/api/settings/providers")
        data = list_response.json()
        assert len(data) == 1
        assert data[0]["is_default"] is True


class TestTestProvider:
    """Tests for POST /api/settings/providers/{provider_id}/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_provider_success(self, test_client, test_ai_provider):
        """Test provider connection test succeeds."""
        with patch("app.api.routes.settings.get_ai_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.health_check = AsyncMock(return_value=True)
            mock_get.return_value = mock_provider

            response = await test_client.post(f"/api/settings/providers/{test_ai_provider.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "successfully" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_test_provider_failure(self, test_client, test_ai_provider):
        """Test provider connection test fails."""
        with patch("app.api.routes.settings.get_ai_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.health_check = AsyncMock(return_value=False)
            mock_get.return_value = mock_provider

            response = await test_client.post(f"/api/settings/providers/{test_ai_provider.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    @pytest.mark.asyncio
    async def test_test_provider_not_found(self, test_client):
        """Test testing non-existent provider returns 404."""
        fake_id = uuid4()
        response = await test_client.post(f"/api/settings/providers/{fake_id}/test")

        assert response.status_code == 404


class TestColors:
    """Tests for color settings endpoints."""

    @pytest.mark.asyncio
    async def test_list_colors_empty(self, test_client):
        """Test listing colors when none exist."""
        response = await test_client.get("/api/settings/colors")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_colors_with_data(self, test_client, test_color):
        """Test listing configured colors."""
        response = await test_client.get("/api/settings/colors")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_color.name
        assert data[0]["hex_value"] == test_color.hex_value

    @pytest.mark.asyncio
    async def test_update_color_name(self, test_client, test_color):
        """Test updating color name."""
        response = await test_client.patch(
            f"/api/settings/colors/{test_color.id}",
            params={"name": "New Color Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "New Color Name"

    @pytest.mark.asyncio
    async def test_update_color_hex(self, test_client, test_color):
        """Test updating color hex value."""
        response = await test_client.patch(
            f"/api/settings/colors/{test_color.id}",
            params={"hex_value": "#00FF00"},
        )

        assert response.status_code == 200
        assert response.json()["hex_value"] == "#00FF00"

    @pytest.mark.asyncio
    async def test_update_color_not_found(self, test_client):
        """Test updating non-existent color returns 404."""
        fake_id = uuid4()
        response = await test_client.patch(
            f"/api/settings/colors/{fake_id}",
            params={"name": "Test"},
        )

        assert response.status_code == 404


class TestPrompts:
    """Tests for prompt settings endpoints."""

    @pytest.mark.asyncio
    async def test_get_summary_prompt(self, test_client):
        """Test getting the summary prompt."""
        response = await test_client.get("/api/settings/prompts/summary")

        assert response.status_code == 200
        data = response.json()
        assert "system_prompt" in data
        assert "user_prompt" in data
        assert len(data["system_prompt"]) > 0
        assert len(data["user_prompt"]) > 0
