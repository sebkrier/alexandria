"""
Shared helper functions for article processing.

These functions are used by both the HTMX routes (HTML templates)
and the JSON API routes for consistent article handling.
"""

from app.models.article import SourceType
from app.schemas.article import MediaType

# =============================================================================
# URL Indicators for Media Type Detection
# =============================================================================

# Platforms that indicate newsletter content
NEWSLETTER_INDICATORS = [
    "substack.com",
    "/p/",  # Common newsletter URL pattern
]

# Platforms that indicate blog content
BLOG_INDICATORS = [
    "medium.com",
    "dev.to",
    "hashnode.",
    "wordpress.com",
    "/blog/",
    ".blog.",
    "blogger.com",
    "ghost.io",
]

# Platforms that indicate academic/research paper content
PAPER_INDICATORS = [
    "arxiv.org",
    "doi.org",
    "nature.com",
    "science.org",
    "ieee.org",
    "acm.org",
    "springer.com",
    "wiley.com",
    "researchgate.net",
    "semanticscholar.org",
    ".edu/",
    "pubmed",
    "ncbi.nlm.nih.gov",
]


# =============================================================================
# Helper Functions
# =============================================================================


def calculate_reading_time(word_count: int | None) -> int | None:
    """
    Calculate estimated reading time in minutes.

    Based on average adult reading speed of 200 words per minute.
    Returns at least 1 minute for any non-empty content.

    Args:
        word_count: Number of words in the article, or None if unknown

    Returns:
        Estimated reading time in minutes, or None if word_count is None
    """
    if word_count is None:
        return None
    return max(1, round(word_count / 200))


def determine_media_type(source_type: SourceType, original_url: str | None) -> MediaType:
    """
    Determine the user-friendly media type from source type and URL.

    Analyzes the source type and URL patterns to categorize content
    as article, paper, video, blog, pdf, or newsletter.

    Args:
        source_type: The source type enum from the Article model
        original_url: The original URL of the article (may be None)

    Returns:
        MediaType enum value indicating the content type
    """
    # Direct mappings from source_type
    if source_type == SourceType.ARXIV:
        return MediaType.PAPER
    if source_type == SourceType.VIDEO:
        return MediaType.VIDEO
    if source_type == SourceType.PDF:
        return MediaType.PDF

    # For URL source type, look at the URL to determine more specific type
    if source_type == SourceType.URL and original_url:
        url_lower = original_url.lower()

        # Check for newsletter platforms
        if any(indicator in url_lower for indicator in NEWSLETTER_INDICATORS):
            return MediaType.NEWSLETTER

        # Check for blog platforms
        if any(indicator in url_lower for indicator in BLOG_INDICATORS):
            return MediaType.BLOG

        # Check for academic/paper platforms
        if any(indicator in url_lower for indicator in PAPER_INDICATORS):
            return MediaType.PAPER

    # Default to article
    return MediaType.ARTICLE


def determine_media_type_str(source_type: SourceType, original_url: str | None) -> str:
    """
    Determine the user-friendly media type as a string.

    Convenience wrapper around determine_media_type() that returns
    a string instead of MediaType enum. Useful for templates.

    Args:
        source_type: The source type enum from the Article model
        original_url: The original URL of the article (may be None)

    Returns:
        String value of the media type (e.g., "article", "paper", "video")
    """
    return determine_media_type(source_type, original_url).value
