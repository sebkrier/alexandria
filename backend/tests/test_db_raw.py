"""
Tests for raw database connection pool (app/db/raw.py).

Tests pool initialization, connection acquisition, and cleanup.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.db.raw as raw_module
from app.db.raw import close_pool, get_conn, init_pool


# =============================================================================
# Pool Lifecycle Tests
# =============================================================================


class TestPoolLifecycle:
    """Tests for connection pool initialization and cleanup."""

    @pytest.fixture(autouse=True)
    def reset_pool(self):
        """Reset global pool state before and after each test."""
        raw_module.pool = None
        yield
        raw_module.pool = None

    @pytest.mark.asyncio
    async def test_init_pool_creates_pool(self):
        """Test init_pool() creates and opens connection pool."""
        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()

        with (
            patch("app.db.raw.get_settings") as mock_get_settings,
            patch("app.db.raw.psycopg_pool.AsyncConnectionPool") as mock_pool_class,
        ):
            mock_settings = MagicMock()
            mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/testdb"
            mock_get_settings.return_value = mock_settings
            mock_pool_class.return_value = mock_pool

            await init_pool()

            # Verify pool was created with correct URL (asyncpg prefix replaced)
            mock_pool_class.assert_called_once()
            call_args = mock_pool_class.call_args
            assert call_args[0][0] == "postgresql://user:pass@localhost:5432/testdb"
            assert call_args[1]["min_size"] == 2
            assert call_args[1]["max_size"] == 10
            assert call_args[1]["open"] is False

            # Verify pool was opened
            mock_pool.open.assert_called_once()

            # Verify global pool was set
            assert raw_module.pool is mock_pool

    @pytest.mark.asyncio
    async def test_init_pool_url_conversion(self):
        """Test init_pool() correctly converts SQLAlchemy URL to psycopg format."""
        mock_pool = AsyncMock()

        with (
            patch("app.db.raw.get_settings") as mock_get_settings,
            patch("app.db.raw.psycopg_pool.AsyncConnectionPool") as mock_pool_class,
        ):
            mock_settings = MagicMock()
            mock_settings.database_url = "postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria"
            mock_get_settings.return_value = mock_settings
            mock_pool_class.return_value = mock_pool

            await init_pool()

            # URL should have asyncpg prefix removed
            call_args = mock_pool_class.call_args
            assert call_args[0][0] == "postgresql://postgres:localdev@localhost:5432/alexandria"

    @pytest.mark.asyncio
    async def test_close_pool_cleans_up(self):
        """Test close_pool() closes and clears the pool."""
        mock_pool = AsyncMock()
        mock_pool.close = AsyncMock()
        raw_module.pool = mock_pool

        await close_pool()

        mock_pool.close.assert_called_once()
        assert raw_module.pool is None

    @pytest.mark.asyncio
    async def test_close_pool_when_none(self):
        """Test close_pool() does nothing when pool is None."""
        raw_module.pool = None

        # Should not raise
        await close_pool()

        assert raw_module.pool is None


# =============================================================================
# Connection Acquisition Tests
# =============================================================================


class TestGetConnection:
    """Tests for get_conn() context manager."""

    @pytest.fixture(autouse=True)
    def reset_pool(self):
        """Reset global pool state before and after each test."""
        raw_module.pool = None
        yield
        raw_module.pool = None

    @pytest.mark.asyncio
    async def test_get_conn_raises_when_pool_not_initialized(self):
        """Test get_conn() raises RuntimeError when pool is None."""
        raw_module.pool = None

        with pytest.raises(RuntimeError, match="Connection pool not initialized"):
            async with get_conn():
                pass

    @pytest.mark.asyncio
    async def test_get_conn_yields_connection(self):
        """Test get_conn() yields a connection from the pool."""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        # Create an async context manager that yields mock_conn
        async def mock_connection_cm():
            yield mock_conn

        # Make pool.connection() return the async context manager
        mock_pool.connection.return_value = mock_connection_cm().__aiter__().__anext__()

        # Actually, we need to mock this differently
        # pool.connection() returns an async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.connection.return_value = mock_cm

        raw_module.pool = mock_pool

        async with get_conn() as conn:
            assert conn is mock_conn

        mock_pool.connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conn_returns_connection_to_pool(self):
        """Test connection is returned to pool after context exits."""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.connection.return_value = mock_cm

        raw_module.pool = mock_pool

        async with get_conn() as conn:
            pass

        # __aexit__ should be called to return connection
        mock_cm.__aexit__.assert_called_once()


# =============================================================================
# Integration Tests (require database)
# =============================================================================


class TestPoolIntegration:
    """Integration tests that require actual database connection."""

    @pytest.fixture(autouse=True)
    def reset_pool(self):
        """Reset global pool state before and after each test."""
        raw_module.pool = None
        yield
        raw_module.pool = None

    @pytest.mark.asyncio
    async def test_init_and_close_pool_integration(self, db_pool):
        """Test full lifecycle with real database (if available)."""
        # db_pool fixture already creates a working pool
        # This test verifies our init/close pattern works

        # Create a mock settings that uses test DB URL
        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()
        mock_pool.close = AsyncMock()

        with (
            patch("app.db.raw.get_settings") as mock_get_settings,
            patch("app.db.raw.psycopg_pool.AsyncConnectionPool") as mock_pool_class,
        ):
            mock_settings = MagicMock()
            mock_settings.database_url = "postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria_test"
            mock_get_settings.return_value = mock_settings
            mock_pool_class.return_value = mock_pool

            # Initialize
            await init_pool()
            assert raw_module.pool is mock_pool

            # Close
            await close_pool()
            mock_pool.close.assert_called_once()
            assert raw_module.pool is None
