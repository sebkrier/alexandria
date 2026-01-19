"""
Background task functions.
"""

from app.tasks.article_processing import process_article_background

__all__ = ["process_article_background"]
