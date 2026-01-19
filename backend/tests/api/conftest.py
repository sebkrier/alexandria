"""
API-specific test fixtures for mocking external services.

These fixtures mock out external dependencies like content extraction,
AI services, and embedding generation to enable fast, isolated tests.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from app.ai.base import CategoryInfo, CategorySuggestion, Summary, TagSuggestion
from app.extractors.base import ExtractedContent


# =============================================================================
# Mock Data Factories
# =============================================================================


def make_extracted_content(
    title: str = "Test Article",
    text: str = "This is the extracted article content.",
    source_type: str = "url",
    url: str = "https://example.com/test",
    authors: list[str] | None = None,
) -> ExtractedContent:
    """Create a mock ExtractedContent object."""
    return ExtractedContent(
        title=title,
        text=text,
        source_type=source_type,
        original_url=url,
        authors=authors or ["Test Author"],
        publication_date=datetime(2025, 1, 15),
        metadata={"word_count": len(text.split())},
    )


def make_summary(
    abstract: str = "A brief summary of the article.",
    markdown: str = "## Summary\n\nThis article discusses important topics.",
) -> Summary:
    """Create a mock Summary object."""
    return Summary(abstract=abstract, markdown=markdown)


def make_tag_suggestions(count: int = 3) -> list[TagSuggestion]:
    """Create a list of mock TagSuggestion objects."""
    tag_names = ["machine-learning", "ai", "technology", "research", "python"]
    return [
        TagSuggestion(
            name=tag_names[i % len(tag_names)],
            confidence=0.9 - (i * 0.1),
            reasoning=f"Tag {i + 1} reasoning",
        )
        for i in range(count)
    ]


def make_category_suggestion(
    category_name: str = "Technology",
    subcategory_name: str = "AI & Machine Learning",
    is_new: bool = False,
) -> CategorySuggestion:
    """Create a mock CategorySuggestion object."""
    return CategorySuggestion(
        category=CategoryInfo(name=category_name, is_new=is_new),
        subcategory=CategoryInfo(name=subcategory_name, is_new=is_new),
        confidence=0.85,
        reasoning="Article is about AI technology",
    )


def make_embedding(dims: int = 768) -> list[float]:
    """Create a mock embedding vector."""
    return [0.1] * dims


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_extract_content():
    """Mock the extract_content function to avoid network calls."""
    with patch("app.extractors.extract_content") as mock:
        mock.return_value = make_extracted_content()
        yield mock


@pytest.fixture
def mock_extract_content_failure():
    """Mock extract_content to raise an exception."""
    with patch("app.extractors.extract_content") as mock:
        mock.side_effect = Exception("Failed to extract content")
        yield mock


@pytest.fixture
def mock_ai_service():
    """Mock the AIService class."""
    with patch("app.ai.service.AIService") as mock_class:
        mock_instance = MagicMock()
        mock_instance.process_article = AsyncMock(return_value=None)
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_ai_provider():
    """Mock an AI provider with all methods."""
    provider = MagicMock()
    provider.health_check = AsyncMock(return_value=True)
    provider.summarize = AsyncMock(return_value=make_summary())
    provider.suggest_tags = AsyncMock(return_value=make_tag_suggestions())
    provider.suggest_category = AsyncMock(return_value=make_category_suggestion())
    provider.answer_question = AsyncMock(return_value="This is the AI's answer.")
    return provider


@pytest.fixture
def mock_get_ai_provider(mock_ai_provider):
    """Mock the get_ai_provider factory function."""
    with patch("app.ai.factory.get_ai_provider") as mock:
        mock.return_value = mock_ai_provider
        yield mock


@pytest.fixture
def mock_get_default_provider(mock_ai_provider):
    """Mock the get_default_provider factory function."""
    with patch("app.ai.factory.get_default_provider") as mock:
        mock.return_value = mock_ai_provider
        yield mock


@pytest.fixture
def mock_generate_embedding():
    """Mock the embedding generation function."""
    with patch("app.ai.embeddings.generate_embedding") as mock:
        mock.return_value = make_embedding()
        yield mock


@pytest.fixture
def mock_generate_query_embedding():
    """Mock the query embedding generation function."""
    with patch("app.ai.embeddings.generate_query_embedding") as mock:
        mock.return_value = make_embedding()
        yield mock


@pytest.fixture
def mock_background_tasks():
    """Mock FastAPI BackgroundTasks to capture added tasks."""
    mock = MagicMock()
    mock.tasks = []

    def add_task(func, *args, **kwargs):
        mock.tasks.append((func, args, kwargs))

    mock.add_task = add_task
    return mock


# =============================================================================
# Composite Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_article_creation(mock_extract_content, mock_ai_service):
    """
    Mock all dependencies needed for article creation.

    Combines content extraction and AI processing mocks.
    """
    return {
        "extract_content": mock_extract_content,
        "ai_service": mock_ai_service,
    }


@pytest.fixture
def mock_ask_question(mock_get_default_provider, mock_generate_query_embedding):
    """
    Mock all dependencies needed for the ask/RAG endpoint.

    Combines provider and embedding mocks.
    """
    return {
        "provider": mock_get_default_provider,
        "embedding": mock_generate_query_embedding,
    }
