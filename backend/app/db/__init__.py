"""Database utilities using psycopg3 for parameterized queries."""

from app.db.raw import init_pool, close_pool, get_conn
from app.db.queries import (
    get_article_count,
    get_category_counts,
    search_articles_semantic,
    bulk_delete_articles,
    bulk_move_articles,
)

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
