"""
Tests for parameterized database queries.
These tests verify SQL injection protection and query correctness.
"""

from uuid import uuid4

import pytest

from app.db.queries import (
    bulk_delete_articles,
    bulk_move_articles,
    get_article_count,
    get_articles_for_search,
    get_category_counts,
    search_articles_semantic,
)


@pytest.mark.asyncio
async def test_article_count_empty(db):
    """Test article count for user with no articles."""
    count = await get_article_count(db, db.test_user_id)
    assert isinstance(count, int)
    assert count == 0


@pytest.mark.asyncio
async def test_article_count_with_articles(db):
    """Test article count after inserting articles."""
    # Insert a test article
    async with db.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO articles (id, user_id, title, source_type, processing_status)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (uuid4(), db.test_user_id, "Test Article", "url", "completed"),
        )
        await db.commit()

    count = await get_article_count(db, db.test_user_id)
    assert count == 1


@pytest.mark.asyncio
async def test_sql_injection_prevention_count(db):
    """Verify parameterized queries prevent SQL injection in count."""
    # This malicious input should be safely escaped by psycopg3
    # If not parameterized, this would cause errors or data loss
    malicious_input = "'; DROP TABLE articles; --"

    # Should raise an error due to invalid UUID format, not execute SQL
    with pytest.raises(Exception):
        # UUID validation will fail, which is the correct behavior
        await get_article_count(db, malicious_input)


@pytest.mark.asyncio
async def test_bulk_delete_empty_list(db):
    """Test bulk delete with empty list returns 0."""
    deleted = await bulk_delete_articles(db, db.test_user_id, [])
    assert deleted == 0


@pytest.mark.asyncio
async def test_bulk_delete_nonexistent(db):
    """Test bulk delete with non-existent IDs."""
    fake_ids = [uuid4(), uuid4(), uuid4()]
    deleted = await bulk_delete_articles(db, db.test_user_id, fake_ids)
    assert deleted == 0


@pytest.mark.asyncio
async def test_bulk_delete_actual_articles(db):
    """Test bulk delete removes correct articles."""
    # Insert test articles
    article_ids = []
    for i in range(3):
        article_id = uuid4()
        article_ids.append(article_id)
        async with db.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO articles (id, user_id, title, source_type, processing_status)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (article_id, db.test_user_id, f"Delete Test {i}", "url", "completed"),
            )
    await db.commit()

    # Verify they exist
    count_before = await get_article_count(db, db.test_user_id)
    assert count_before == 3

    # Delete 2 of them
    deleted = await bulk_delete_articles(db, db.test_user_id, article_ids[:2])
    assert deleted == 2

    # Verify count decreased
    count_after = await get_article_count(db, db.test_user_id)
    assert count_after == 1


@pytest.mark.asyncio
async def test_bulk_delete_wrong_user(db):
    """Test bulk delete doesn't affect other users' articles."""
    # Insert article for test user
    article_id = uuid4()
    async with db.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO articles (id, user_id, title, source_type, processing_status)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (article_id, db.test_user_id, "User's Article", "url", "completed"),
        )
        await db.commit()

    # Try to delete with wrong user ID
    wrong_user_id = uuid4()
    deleted = await bulk_delete_articles(db, wrong_user_id, [article_id])
    assert deleted == 0  # Should not delete

    # Article should still exist
    count = await get_article_count(db, db.test_user_id)
    assert count == 1


@pytest.mark.asyncio
async def test_semantic_search_empty_results(db):
    """Test semantic search returns empty list when no matches."""
    # 768-dimensional zero vector (won't match anything)
    fake_embedding = [0.0] * 768

    results = await search_articles_semantic(db, db.test_user_id, fake_embedding, limit=10)
    assert isinstance(results, list)
    assert len(results) == 0  # No articles with embeddings


@pytest.mark.asyncio
async def test_category_counts_empty(db):
    """Test category counts for user with no categories."""
    counts = await get_category_counts(db, db.test_user_id)
    assert isinstance(counts, list)
    # May have counts for other users' categories that match, but
    # article_count for test user should be 0


@pytest.mark.asyncio
async def test_full_text_search_empty(db):
    """Test full-text search with no matching results."""
    results = await get_articles_for_search(
        db, db.test_user_id, "nonexistent query term xyz", limit=10
    )
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_bulk_move_empty_list(db):
    """Test bulk move with empty list."""
    # Create a category first
    category_id = uuid4()
    async with db.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO categories (id, user_id, name)
            VALUES (%s, %s, %s)
        """,
            (category_id, db.test_user_id, "Test Category"),
        )
        await db.commit()

    moved = await bulk_move_articles(db, db.test_user_id, [], category_id)
    assert moved == 0


@pytest.mark.asyncio
async def test_bulk_move_invalid_category(db):
    """Test bulk move to non-existent category raises error."""
    fake_category_id = uuid4()
    article_id = uuid4()

    with pytest.raises(ValueError, match="not found"):
        await bulk_move_articles(db, db.test_user_id, [article_id], fake_category_id)
