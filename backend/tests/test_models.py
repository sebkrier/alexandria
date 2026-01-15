"""
Tests for Pydantic models and data validation.
These tests don't require API keys or database connections.
"""

import pytest
from pydantic import ValidationError

from app.ai.base import CategoryInfo, CategorySuggestion, Summary, TagSuggestion
from app.ai.llm import PROVIDER_MODELS


class TestSummaryModel:
    """Tests for Summary Pydantic model."""

    def test_summary_from_markdown_extracts_abstract(self):
        """Test that from_markdown extracts one-line summary."""
        markdown = """## One-Line Summary
This is a one-line summary of the article.

## Full Summary
This is the full summary with more details about the article content.
It spans multiple paragraphs and provides comprehensive coverage.
"""
        summary = Summary.from_markdown(markdown, "Test Title")
        assert "one-line summary" in summary.abstract.lower()
        assert summary.markdown == markdown

    def test_summary_from_markdown_fallback(self):
        """Test fallback when no one-line summary section exists."""
        markdown = """This article discusses important topics.

It has multiple paragraphs but no explicit summary section.
The content is still valuable and should be captured.
"""
        summary = Summary.from_markdown(markdown, "Test")
        assert len(summary.abstract) > 0
        assert summary.markdown == markdown

    def test_summary_to_markdown(self):
        """Test to_markdown returns original markdown."""
        original = "# Test\n\nSome content"
        summary = Summary(markdown=original, abstract="test")
        assert summary.to_markdown() == original


class TestTagSuggestion:
    """Tests for TagSuggestion model."""

    def test_valid_tag_suggestion(self):
        """Test creating valid tag suggestion."""
        tag = TagSuggestion(
            name="machine-learning", confidence=0.95, reasoning="Article discusses ML concepts"
        )
        assert tag.name == "machine-learning"
        assert tag.confidence == 0.95

    def test_tag_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TagSuggestion(
                name="test",
                confidence=1.5,  # Invalid: > 1
                reasoning="test",
            )

        with pytest.raises(ValidationError):
            TagSuggestion(
                name="test",
                confidence=-0.1,  # Invalid: < 0
                reasoning="test",
            )

    def test_tag_edge_confidence(self):
        """Test edge case confidence values."""
        tag_zero = TagSuggestion(name="test", confidence=0.0, reasoning="test")
        assert tag_zero.confidence == 0.0

        tag_one = TagSuggestion(name="test", confidence=1.0, reasoning="test")
        assert tag_one.confidence == 1.0


class TestCategorySuggestion:
    """Tests for CategorySuggestion model."""

    def test_valid_category_suggestion(self):
        """Test creating valid two-level category suggestion."""
        suggestion = CategorySuggestion(
            category=CategoryInfo(name="Technology", is_new=False),
            subcategory=CategoryInfo(name="Machine Learning", is_new=True),
            confidence=0.85,
            reasoning="Article is about ML techniques",
        )
        assert suggestion.category.name == "Technology"
        assert suggestion.subcategory.name == "Machine Learning"
        assert suggestion.subcategory.is_new is True

    def test_legacy_properties(self):
        """Test backward-compatible legacy properties."""
        suggestion = CategorySuggestion(
            category=CategoryInfo(name="Science", is_new=False),
            subcategory=CategoryInfo(name="Physics", is_new=False),
            confidence=0.9,
            reasoning="test",
        )
        # Legacy properties for backward compatibility
        assert suggestion.category_name == "Physics"  # Returns subcategory
        assert suggestion.parent_category == "Science"  # Returns category

    def test_is_new_category_any(self):
        """Test is_new_category returns True if either level is new."""
        # Only parent new
        s1 = CategorySuggestion(
            category=CategoryInfo(name="New Cat", is_new=True),
            subcategory=CategoryInfo(name="Existing", is_new=False),
            confidence=0.8,
            reasoning="test",
        )
        assert s1.is_new_category is True

        # Only child new
        s2 = CategorySuggestion(
            category=CategoryInfo(name="Existing", is_new=False),
            subcategory=CategoryInfo(name="New Sub", is_new=True),
            confidence=0.8,
            reasoning="test",
        )
        assert s2.is_new_category is True

        # Both existing
        s3 = CategorySuggestion(
            category=CategoryInfo(name="Existing", is_new=False),
            subcategory=CategoryInfo(name="Also Existing", is_new=False),
            confidence=0.8,
            reasoning="test",
        )
        assert s3.is_new_category is False


class TestProviderModels:
    """Tests for provider model configurations."""

    def test_anthropic_models_available(self):
        """Test Anthropic models are configured."""
        assert "anthropic" in PROVIDER_MODELS
        assert len(PROVIDER_MODELS["anthropic"]) >= 3
        assert "claude-sonnet-4-20250514" in PROVIDER_MODELS["anthropic"]

    def test_openai_models_available(self):
        """Test OpenAI models are configured."""
        assert "openai" in PROVIDER_MODELS
        assert len(PROVIDER_MODELS["openai"]) >= 2
        assert "gpt-4o" in PROVIDER_MODELS["openai"]

    def test_google_models_available(self):
        """Test Google models are configured."""
        assert "google" in PROVIDER_MODELS
        assert len(PROVIDER_MODELS["google"]) >= 2
