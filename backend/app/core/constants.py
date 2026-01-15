"""
Application-wide constants.

Centralizes magic numbers and strings to improve maintainability.
"""

# =============================================================================
# AI/ML Configuration
# =============================================================================

# Embedding model configuration
EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIMENSION = 768
EMBEDDING_MAX_CHARS = 8000

# AI confidence thresholds
TAG_CONFIDENCE_THRESHOLD = 0.7
CATEGORY_CONFIDENCE_THRESHOLD = 0.5

# AI generation limits
MAX_TAGS_PER_ARTICLE = 7
MAX_SUMMARY_TOKENS = 2000
MAX_TAGS_TOKENS = 1000
MAX_CATEGORY_TOKENS = 500
MAX_QA_TOKENS = 1500

# Default AI parameters
DEFAULT_TEMPERATURE = 0.3

# =============================================================================
# Search Configuration
# =============================================================================

# Semantic search
SEMANTIC_SEARCH_LIMIT = 10
KEYWORD_SEARCH_LIMIT = 10
HYBRID_SEARCH_TOP_N = 15

# Query processing
MAX_SEARCH_WORDS = 10
TITLE_MATCH_MAX_WORDS = 5

# =============================================================================
# Pagination Defaults
# =============================================================================

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# =============================================================================
# Date/Time Constants
# =============================================================================

DAYS_IN_WEEK = 7
DEFAULT_RECENT_ARTICLES_LIMIT = 10

# =============================================================================
# Database Configuration
# =============================================================================

DB_POOL_MIN_SIZE = 2
DB_POOL_MAX_SIZE = 10

# =============================================================================
# Content Processing
# =============================================================================

MAX_TEXT_LENGTH = 100_000  # Max chars for extracted text
TITLE_TRUNCATE_LENGTH = 50
MAX_ERRORS_IN_RESPONSE = 5

# =============================================================================
# External API Endpoints
# =============================================================================

LESSWRONG_GRAPHQL_ENDPOINT = "https://www.lesswrong.com/graphql"

# =============================================================================
# Error Messages
# =============================================================================

class ErrorMessages:
    """Standardized error messages for HTTP exceptions."""

    ARTICLE_NOT_FOUND = "Article not found"
    CATEGORY_NOT_FOUND = "Category not found"
    TAG_NOT_FOUND = "Tag not found"
    NOTE_NOT_FOUND = "Note not found"
    PROVIDER_NOT_FOUND = "AI provider not found"
    COLOR_NOT_FOUND = "Color not found"

    INVALID_URL = "Failed to extract content from URL"
    INVALID_PDF = "Failed to extract content from PDF"
    PROCESSING_FAILED = "Article processing failed"
    AI_PROVIDER_REQUIRED = "No AI provider configured"

    UNAUTHORIZED = "Not authorized to access this resource"
    DUPLICATE_ENTRY = "Entry already exists"
