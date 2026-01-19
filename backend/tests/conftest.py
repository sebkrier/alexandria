"""
Pytest fixtures for Alexandria tests.

This module provides two sets of fixtures:
1. Raw psycopg fixtures (db_pool, db) - for low-level database tests
2. SQLAlchemy fixtures (async_db_session, test_client) - for API route tests
"""

import os
from typing import AsyncGenerator
from uuid import uuid4

import psycopg_pool
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test database URL - uses separate test database
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:localdev@localhost:5432/alexandria_test"
)

# SQLAlchemy async URL format
TEST_DATABASE_URL_ASYNC = os.environ.get(
    "TEST_DATABASE_URL_ASYNC",
    "postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria_test",
)

# Check if database is available
_db_available = None


async def check_db_available():
    """Check if the test database is accessible."""
    global _db_available
    if _db_available is not None:
        return _db_available

    try:
        pool = psycopg_pool.AsyncConnectionPool(TEST_DB_URL, min_size=1, max_size=1, open=False)
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
            await cur.execute(
                """
                INSERT INTO users (id, email, password_hash)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id
                RETURNING id
            """,
                (test_user_id, test_email, "fakehash"),
            )
            row = await cur.fetchone()
            conn.test_user_id = row[0]
            await conn.commit()

        yield conn

        # Cleanup - delete test data
        # Rollback any aborted transaction before cleanup (e.g., from expected test failures)
        await conn.rollback()
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM articles WHERE user_id = %s", (conn.test_user_id,))
            await cur.execute("DELETE FROM categories WHERE user_id = %s", (conn.test_user_id,))
            await cur.execute("DELETE FROM tags WHERE user_id = %s", (conn.test_user_id,))
            await cur.execute("DELETE FROM users WHERE id = %s", (conn.test_user_id,))
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


# =============================================================================
# SQLAlchemy Fixtures for API Testing
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a SQLAlchemy async engine for testing."""
    if not await check_db_available():
        pytest.skip("Test database not available")

    engine = create_async_engine(
        TEST_DATABASE_URL_ASYNC,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create an async SQLAlchemy session for testing.

    Uses a transaction that is rolled back after each test for isolation.
    Also creates a test user that persists for the session.
    """
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        # Import models here to avoid circular imports
        from app.models.user import User

        # Create test user
        test_user = User(
            id=uuid4(),
            email=f"test-{uuid4()}@test.com",
            password_hash="fakehash",
        )
        session.add(test_user)
        await session.commit()

        # Store user on session for access in tests
        session.test_user = test_user

        yield session

        # Cleanup: delete all data created by this test user
        try:
            await session.rollback()  # Rollback any uncommitted changes

            from app.models.ai_provider import AIProvider
            from app.models.article import Article
            from app.models.article_category import ArticleCategory
            from app.models.article_tag import ArticleTag
            from app.models.category import Category
            from app.models.color import Color
            from app.models.note import Note
            from app.models.tag import Tag

            # Delete in correct order to respect foreign keys
            from sqlalchemy import delete, select

            # Get article IDs for this user
            article_ids_result = await session.execute(
                select(Article.id).where(Article.user_id == test_user.id)
            )
            article_ids = [row[0] for row in article_ids_result.all()]

            # Delete related data
            if article_ids:
                await session.execute(delete(Note).where(Note.article_id.in_(article_ids)))
                await session.execute(delete(ArticleCategory).where(ArticleCategory.article_id.in_(article_ids)))
                await session.execute(delete(ArticleTag).where(ArticleTag.article_id.in_(article_ids)))

            await session.execute(delete(Article).where(Article.user_id == test_user.id))
            await session.execute(delete(Category).where(Category.user_id == test_user.id))
            await session.execute(delete(Tag).where(Tag.user_id == test_user.id))
            await session.execute(delete(Color).where(Color.user_id == test_user.id))
            await session.execute(delete(AIProvider).where(AIProvider.user_id == test_user.id))
            await session.execute(delete(User).where(User.id == test_user.id))
            await session.commit()
        except Exception:
            # Cleanup errors are not critical - tests already passed/failed
            pass


@pytest_asyncio.fixture
async def test_user(async_db_session: AsyncSession):
    """Get the test user from the session."""
    return async_db_session.test_user


@pytest_asyncio.fixture
async def test_client(async_db_session: AsyncSession, test_user) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an httpx AsyncClient for testing API routes.

    Overrides FastAPI dependencies to use the test session and user.
    """
    from app.database import get_db
    from app.main import app
    from app.utils.auth import get_current_user

    # Override dependencies
    async def override_get_db():
        yield async_db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


# =============================================================================
# Test Data Factory Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def test_article(async_db_session: AsyncSession, test_user):
    """Create a test article in the database."""
    from app.models.article import Article, ProcessingStatus, SourceType

    article = Article(
        user_id=test_user.id,
        source_type=SourceType.URL,
        original_url="https://example.com/test-article",
        title="Test Article",
        extracted_text="This is test content for the article.",
        word_count=8,
        processing_status=ProcessingStatus.COMPLETED,
        summary="A test summary.",
    )
    async_db_session.add(article)
    await async_db_session.commit()
    await async_db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def test_category(async_db_session: AsyncSession, test_user):
    """Create a test category in the database."""
    from app.models.category import Category

    category = Category(
        user_id=test_user.id,
        name="Test Category",
        position=0,
    )
    async_db_session.add(category)
    await async_db_session.commit()
    await async_db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_tag(async_db_session: AsyncSession, test_user):
    """Create a test tag in the database."""
    from app.models.tag import Tag

    tag = Tag(
        user_id=test_user.id,
        name="test-tag",
        color="#FF5733",
    )
    async_db_session.add(tag)
    await async_db_session.commit()
    await async_db_session.refresh(tag)
    return tag


@pytest_asyncio.fixture
async def test_color(async_db_session: AsyncSession, test_user):
    """Create a test color in the database."""
    from app.models.color import Color

    color = Color(
        user_id=test_user.id,
        name="Test Color",
        hex_value="#FF0000",
        position=0,
    )
    async_db_session.add(color)
    await async_db_session.commit()
    await async_db_session.refresh(color)
    return color


@pytest_asyncio.fixture
async def test_ai_provider(async_db_session: AsyncSession, test_user):
    """Create a test AI provider in the database."""
    from app.models.ai_provider import AIProvider, ProviderName
    from app.utils.encryption import encrypt_api_key

    provider = AIProvider(
        user_id=test_user.id,
        provider_name=ProviderName.ANTHROPIC,
        display_name="Test Claude",
        model_id="claude-sonnet-4-20250514",
        api_key_encrypted=encrypt_api_key("sk-test-key-12345"),
        is_default=True,
        is_active=True,
    )
    async_db_session.add(provider)
    await async_db_session.commit()
    await async_db_session.refresh(provider)
    return provider
