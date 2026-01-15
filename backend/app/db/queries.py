"""
Parameterized SQL queries using psycopg3.
All queries use proper parameterization to prevent SQL injection.
"""

import logging
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


async def get_article_count(conn: AsyncConnection, user_id: UUID) -> int:
    """
    Count articles for a user.

    Args:
        conn: psycopg3 async connection
        user_id: User's UUID

    Returns:
        Number of articles
    """
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM articles WHERE user_id = %s", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_category_counts(conn: AsyncConnection, user_id: UUID) -> list[dict]:
    """
    Get category article counts for a user.

    Args:
        conn: psycopg3 async connection
        user_id: User's UUID

    Returns:
        List of category dicts with article counts
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT c.id, c.name, c.parent_id, COUNT(ac.article_id) as article_count
            FROM categories c
            LEFT JOIN article_categories ac ON ac.category_id = c.id
            LEFT JOIN articles a ON a.id = ac.article_id AND a.user_id = %s
            WHERE c.user_id = %s
            GROUP BY c.id, c.name, c.parent_id
            ORDER BY c.name
        """,
            (user_id, user_id),
        )
        return await cur.fetchall()


async def search_articles_semantic(
    conn: AsyncConnection,
    user_id: UUID,
    query_embedding: list[float],
    limit: int = 15,
) -> list[dict]:
    """
    Semantic search for articles using vector similarity.

    Args:
        conn: psycopg3 async connection
        user_id: User's UUID
        query_embedding: Query embedding vector (768 dimensions)
        limit: Maximum results to return

    Returns:
        List of article dicts with distance scores
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        # Use parameterized query with vector cast
        await cur.execute(
            """
            SELECT
                id,
                title,
                summary,
                source_type,
                original_url,
                embedding <=> %s::vector(768) as distance
            FROM articles
            WHERE user_id = %s
            AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector(768)
            LIMIT %s
        """,
            (query_embedding, user_id, query_embedding, limit),
        )
        return await cur.fetchall()


async def bulk_delete_articles(
    conn: AsyncConnection,
    user_id: UUID,
    article_ids: list[UUID],
) -> int:
    """
    Bulk delete articles by IDs.

    This uses parameterized queries to prevent SQL injection,
    even when dealing with lists of IDs.

    Args:
        conn: psycopg3 async connection
        user_id: User's UUID (for authorization)
        article_ids: List of article UUIDs to delete

    Returns:
        Number of articles deleted
    """
    if not article_ids:
        return 0

    async with conn.cursor() as cur:
        # Use ANY(%s) for array parameter - psycopg3 handles this safely
        await cur.execute(
            """
            DELETE FROM articles
            WHERE user_id = %s AND id = ANY(%s)
        """,
            (user_id, article_ids),
        )
        await conn.commit()
        return cur.rowcount


async def bulk_move_articles(
    conn: AsyncConnection,
    user_id: UUID,
    article_ids: list[UUID],
    category_id: UUID,
) -> int:
    """
    Bulk move articles to a new category.

    Args:
        conn: psycopg3 async connection
        user_id: User's UUID (for authorization)
        article_ids: List of article UUIDs to move
        category_id: Target category UUID

    Returns:
        Number of articles moved
    """
    if not article_ids:
        return 0

    async with conn.cursor() as cur:
        # First verify the category belongs to the user
        await cur.execute(
            "SELECT id FROM categories WHERE id = %s AND user_id = %s", (category_id, user_id)
        )
        if not await cur.fetchone():
            raise ValueError(f"Category {category_id} not found or not owned by user")

        # Remove existing category assignments for these articles
        await cur.execute(
            """
            DELETE FROM article_categories
            WHERE article_id = ANY(%s)
            AND article_id IN (SELECT id FROM articles WHERE user_id = %s)
        """,
            (article_ids, user_id),
        )

        # Add new category assignments
        await cur.executemany(
            """
            INSERT INTO article_categories (article_id, category_id, is_primary, suggested_by_ai)
            SELECT %s, %s, true, false
            WHERE EXISTS (SELECT 1 FROM articles WHERE id = %s AND user_id = %s)
        """,
            [(aid, category_id, aid, user_id) for aid in article_ids],
        )

        await conn.commit()
        return len(article_ids)


async def get_articles_for_search(
    conn: AsyncConnection,
    user_id: UUID,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """
    Full-text search for articles using PostgreSQL tsvector.

    Args:
        conn: psycopg3 async connection
        user_id: User's UUID
        query: Search query string
        limit: Maximum results

    Returns:
        List of matching articles
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT
                id,
                title,
                summary,
                source_type,
                original_url,
                ts_rank(search_vector, plainto_tsquery('english', %s)) as rank
            FROM articles
            WHERE user_id = %s
            AND search_vector @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
        """,
            (query, user_id, query, limit),
        )
        return await cur.fetchall()
