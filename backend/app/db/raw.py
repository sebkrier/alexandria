"""
Raw database connection pool using psycopg3.
Provides parameterized query support for security-critical operations.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg_pool
from psycopg import AsyncConnection

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool
pool: psycopg_pool.AsyncConnectionPool | None = None


async def init_pool() -> None:
    """Initialize the psycopg3 async connection pool."""
    global pool

    settings = get_settings()

    # Convert SQLAlchemy URL format to psycopg format
    # postgresql+asyncpg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    logger.info("Initializing psycopg3 connection pool")
    pool = psycopg_pool.AsyncConnectionPool(
        db_url,
        min_size=2,
        max_size=10,
        open=False,  # Don't open immediately, we'll do it explicitly
    )
    await pool.open()
    logger.info("psycopg3 connection pool initialized")


async def close_pool() -> None:
    """Close the connection pool."""
    global pool
    if pool:
        logger.info("Closing psycopg3 connection pool")
        await pool.close()
        pool = None


@asynccontextmanager
async def get_conn() -> AsyncGenerator[AsyncConnection, None]:
    """
    Get a connection from the pool.

    Usage:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT ...")
    """
    if pool is None:
        raise RuntimeError("Connection pool not initialized. Call init_pool() first.")

    async with pool.connection() as conn:
        yield conn
