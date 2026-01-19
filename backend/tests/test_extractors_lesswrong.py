"""
Tests for the LessWrong extractor (app/extractors/lesswrong.py).

Tests LessWrong/Alignment Forum URL detection, GraphQL API integration,
and content extraction from the API response.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.extractors.lesswrong import LessWrongExtractor


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def extractor():
    """Create a LessWrongExtractor instance."""
    return LessWrongExtractor()


@pytest.fixture
def sample_graphql_response():
    """Sample GraphQL API response for a LessWrong post."""
    return {
        "data": {
            "post": {
                "result": {
                    "_id": "abc123xyz",
                    "title": "Understanding AI Alignment",
                    "slug": "understanding-ai-alignment",
                    "postedAt": "2024-03-15T14:30:00Z",
                    "htmlBody": "<p>This is the HTML body of the post.</p>",
                    "contents": {
                        "markdown": "# Understanding AI Alignment\n\nThis is the markdown content.",
                        "plaintextMainText": "Understanding AI Alignment. This is the plaintext content of the post about AI safety and alignment research.",
                    },
                    "user": {
                        "displayName": "AI Researcher",
                        "username": "ai_researcher",
                    },
                    "coauthors": [
                        {
                            "displayName": "Coauthor One",
                            "username": "coauthor1",
                        },
                        {
                            "displayName": None,
                            "username": "coauthor2",
                        },
                    ],
                }
            }
        }
    }


@pytest.fixture
def sample_graphql_response_minimal():
    """Minimal GraphQL response with only required fields."""
    return {
        "data": {
            "post": {
                "result": {
                    "_id": "minimal123",
                    "title": "Minimal Post",
                    "slug": "minimal-post",
                    "htmlBody": "<p>Content here.</p>",
                    "contents": None,
                    "user": None,
                    "coauthors": None,
                }
            }
        }
    }


# =============================================================================
# can_handle() Tests
# =============================================================================


class TestCanHandle:
    """Tests for LessWrong URL detection."""

    def test_handles_lesswrong_post_url(self):
        """LessWrong post URLs should be handled."""
        assert LessWrongExtractor.can_handle("https://www.lesswrong.com/posts/abc123/post-title")
        assert LessWrongExtractor.can_handle("https://lesswrong.com/posts/xyz789/another-post")

    def test_handles_alignment_forum_post_url(self):
        """Alignment Forum post URLs should be handled."""
        assert LessWrongExtractor.can_handle("https://www.alignmentforum.org/posts/abc123/post-title")
        assert LessWrongExtractor.can_handle("https://alignmentforum.org/posts/def456/alignment-post")

    def test_rejects_lesswrong_non_post_urls(self):
        """Non-post LessWrong URLs should not be handled."""
        assert not LessWrongExtractor.can_handle("https://www.lesswrong.com/users/username")
        assert not LessWrongExtractor.can_handle("https://www.lesswrong.com/tag/ai")
        assert not LessWrongExtractor.can_handle("https://www.lesswrong.com/")

    def test_rejects_non_lesswrong_urls(self):
        """Non-LessWrong URLs should not be handled."""
        assert not LessWrongExtractor.can_handle("https://example.com/posts/abc123")
        assert not LessWrongExtractor.can_handle("https://medium.com/posts/article")


# =============================================================================
# _extract_post_id() Tests
# =============================================================================


class TestExtractPostId:
    """Tests for post ID extraction from URLs."""

    def test_extracts_post_id_from_standard_url(self, extractor):
        """Test extracting post ID from standard URL format."""
        url = "https://www.lesswrong.com/posts/abc123XYZ/post-title-here"
        result = extractor._extract_post_id(url)

        assert result == "abc123XYZ"

    def test_extracts_post_id_from_short_id(self, extractor):
        """Test extracting short post ID."""
        url = "https://www.lesswrong.com/posts/aB1/short"
        result = extractor._extract_post_id(url)

        assert result == "aB1"

    def test_returns_none_for_invalid_url(self, extractor):
        """Test returns None for URLs without post ID."""
        url = "https://www.lesswrong.com/users/username"
        result = extractor._extract_post_id(url)

        assert result is None


# =============================================================================
# extract() Tests - Success Cases
# =============================================================================


class TestExtractSuccess:
    """Tests for successful LessWrong extraction."""

    @pytest.mark.asyncio
    async def test_extract_post_success(self, extractor, sample_graphql_response):
        """Test extracting a LessWrong post."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(
                url="https://www.lesswrong.com/posts/abc123xyz/understanding-ai-alignment"
            )

            assert result.title == "Understanding AI Alignment"
            assert result.source_type == "url"
            assert "AI safety" in result.text or "alignment" in result.text.lower()

    @pytest.mark.asyncio
    async def test_extract_with_authors(self, extractor, sample_graphql_response):
        """Test author extraction including coauthors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/abc123/post")

            assert "AI Researcher" in result.authors
            assert "Coauthor One" in result.authors
            assert "coauthor2" in result.authors  # Falls back to username

    @pytest.mark.asyncio
    async def test_extract_with_publication_date(self, extractor, sample_graphql_response):
        """Test publication date extraction."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/abc123/post")

            assert result.publication_date is not None
            assert result.publication_date.year == 2024
            assert result.publication_date.month == 3
            # Should be timezone-naive
            assert result.publication_date.tzinfo is None

    @pytest.mark.asyncio
    async def test_extract_metadata(self, extractor, sample_graphql_response):
        """Test metadata extraction."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/abc123/post")

            assert result.metadata.get("platform") == "lesswrong"
            assert result.metadata.get("post_id") == "abc123"


# =============================================================================
# extract() Tests - Error Handling
# =============================================================================


class TestExtractErrors:
    """Tests for error handling during extraction."""

    @pytest.mark.asyncio
    async def test_extract_requires_url(self, extractor):
        """Extract should raise ValueError if no URL provided."""
        with pytest.raises(ValueError, match="URL is required"):
            await extractor.extract()

    @pytest.mark.asyncio
    async def test_extract_invalid_url_no_post_id(self, extractor):
        """Test error when URL doesn't contain post ID."""
        with pytest.raises(ValueError, match="Could not extract post ID"):
            await extractor.extract(url="https://www.lesswrong.com/users/username")

    @pytest.mark.asyncio
    async def test_extract_post_not_found(self, extractor):
        """Test error when post is not found in API response."""
        empty_response = {"data": {"post": {"result": None}}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = empty_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError, match="Post not found"):
                await extractor.extract(url="https://www.lesswrong.com/posts/nonexistent/post")

    @pytest.mark.asyncio
    async def test_extract_handles_api_error(self, extractor):
        """Test handling of GraphQL API error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="500 Internal Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await extractor.extract(url="https://www.lesswrong.com/posts/abc123/post")


# =============================================================================
# Content Extraction Tests
# =============================================================================


class TestContentExtraction:
    """Tests for content extraction from API response."""

    @pytest.mark.asyncio
    async def test_prefers_plaintext(self, extractor, sample_graphql_response):
        """Test that plaintextMainText is preferred over markdown."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/abc123/post")

            # Should use plaintextMainText
            assert "plaintext content" in result.text.lower()

    @pytest.mark.asyncio
    async def test_falls_back_to_markdown(self, extractor):
        """Test fallback to markdown when plaintext not available."""
        response = {
            "data": {
                "post": {
                    "result": {
                        "_id": "test",
                        "title": "Test",
                        "contents": {
                            "markdown": "# Markdown Content\n\nThis is markdown.",
                            "plaintextMainText": None,
                        },
                        "user": None,
                        "coauthors": None,
                    }
                }
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/test/post")

            assert "Markdown Content" in result.text or "markdown" in result.text.lower()

    @pytest.mark.asyncio
    async def test_falls_back_to_html_body(self, extractor, sample_graphql_response_minimal):
        """Test fallback to htmlBody when contents is None."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response_minimal
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/minimal123/post")

            assert "Content here" in result.text


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_handles_missing_user(self, extractor, sample_graphql_response_minimal):
        """Test handling of posts without user information."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response_minimal
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/minimal123/post")

            assert result.authors == []

    @pytest.mark.asyncio
    async def test_handles_missing_date(self, extractor):
        """Test handling of posts without postedAt date."""
        response = {
            "data": {
                "post": {
                    "result": {
                        "_id": "test",
                        "title": "Test",
                        "postedAt": None,
                        "htmlBody": "<p>Content</p>",
                        "contents": None,
                        "user": None,
                        "coauthors": None,
                    }
                }
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://www.lesswrong.com/posts/test/post")

            assert result.publication_date is None

    @pytest.mark.asyncio
    async def test_alignment_forum_domain(self, extractor, sample_graphql_response):
        """Test extraction from Alignment Forum domain."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_graphql_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(
                url="https://www.alignmentforum.org/posts/abc123xyz/alignment-post"
            )

            assert result.title is not None
            assert result.metadata.get("domain") == "www.alignmentforum.org"
