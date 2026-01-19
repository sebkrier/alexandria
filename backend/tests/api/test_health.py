"""
Tests for the health check endpoint.

Coverage target: 100% of app/api/routes/health.py
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestHealthCheck:
    """Tests for GET /api/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, test_client):
        """Test health check returns healthy status when DB is connected."""
        response = await test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    @pytest.mark.asyncio
    async def test_health_check_db_error(self, test_client, async_db_session):
        """Test health check returns unhealthy when DB query fails."""
        # Mock the database execute to raise an exception
        with patch.object(
            async_db_session,
            "execute",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection failed"),
        ):
            response = await test_client.get("/api/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "disconnected"
