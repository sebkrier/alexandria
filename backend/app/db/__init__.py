"""Database utilities using psycopg3 for parameterized queries."""

from app.db.queries import (
    bulk_delete_articles,
    bulk_move_articles,
    get_article_count,
    get_category_counts,
    search_articles_semantic,
)
from app.db.raw import close_pool, get_conn, init_pool

__all__ = [
    "init_pool",
    "close_pool",
    "get_conn",
    "get_article_count",
    "get_category_counts",
    "search_articles_semantic",
    "bulk_delete_articles",
    "bulk_move_articles",
]
