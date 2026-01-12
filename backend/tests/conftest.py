"""
Pytest fixtures for Alexandria tests.
"""

import os
import pytest
import pytest_asyncio
from uuid import uuid4

import psycopg_pool
from psycopg import AsyncConnection

# Test database URL - uses separate test database
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:localdev@localhost:5432/alexandria_test"
)

# Check if database is available
_db_available = None


async def check_db_available():
    """Check if the test database is accessible."""
    global _db_available
    if _db_available is not None:
        return _db_available

    try:
        pool = psycopg_pool.AsyncConnectionPool(
            TEST_DB_URL, min_size=1, max_size=1, open=False
        )
        await pool.open(wait=True, timeout=5)
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        await pool.close()
        _db_available = True
    except Exception as e:
        print(f"Test database not available: {e}")
        _db_available = False

    return _db_available


@pytest_asyncio.fixture
async def db_pool():
    """Create a connection pool for testing."""
    if not await check_db_available():
        pytest.skip("Test database not available")

    pool = psycopg_pool.AsyncConnectionPool(
        TEST_DB_URL,
        min_size=1,
        max_size=2,
        open=False,
    )
    await pool.open()
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def db(db_pool: psycopg_pool.AsyncConnectionPool):
    """
    Get a database connection with a test user.
    Creates test user, yields connection, then cleans up.
    """
    async with db_pool.connection() as conn:
        test_user_id = uuid4()
        test_email = f"test-{test_user_id}@test.com"

        # Create test user
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (id, email, hashed_password)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id
                RETURNING id
            """, (test_user_id, test_email, "fakehash"))
            row = await cur.fetchone()
            conn.test_user_id = row[0]
            await conn.commit()

        yield conn

        # Cleanup - delete test data
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM articles WHERE user_id = %s",
                (conn.test_user_id,)
            )
            await cur.execute(
                "DELETE FROM categories WHERE user_id = %s",
                (conn.test_user_id,)
            )
            await cur.execute(
                "DELETE FROM tags WHERE user_id = %s",
                (conn.test_user_id,)
            )
            await cur.execute(
                "DELETE FROM users WHERE id = %s",
                (conn.test_user_id,)
            )
            await conn.commit()


@pytest.fixture
def test_user_id(db: AsyncConnection):
    """Get the test user ID from the database connection."""
    return db.test_user_id


@pytest.fixture
def sample_article_data():
    """Sample article data for testing."""
    return {
        "title": "Test Article: Understanding Transformers",
        "summary": "A test article about transformer architecture in machine learning.",
        "extracted_text": """
        The Transformer architecture has revolutionized natural language processing.
        Introduced in 2017, it uses self-attention mechanisms to process sequences
        in parallel rather than sequentially. This enables much faster training
        and has led to models like BERT, GPT, and their successors.
        """,
        "source_type": "url",
        "original_url": "https://example.com/test-article",
    }
