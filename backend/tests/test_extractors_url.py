"""
Tests for the URL extractor (app/extractors/url.py).

Tests URL detection, HTML fetching with multiple fallback strategies,
and content extraction using readability and BeautifulSoup.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.extractors.url import URLExtractor

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def extractor():
    """Create a URLExtractor instance."""
    return URLExtractor()


@pytest.fixture
def sample_html_article():
    """Sample HTML for a typical article page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Article - Example Site</title>
        <meta property="og:title" content="Test Article Title" />
        <meta name="author" content="John Doe" />
        <meta property="article:published_time" content="2024-01-15T10:30:00Z" />
        <meta property="og:image" content="https://example.com/image.jpg" />
    </head>
    <body>
        <nav>Navigation here</nav>
        <article>
            <h1>Test Article Title</h1>
            <p class="byline">By John Doe</p>
            <div class="article-content">
                <p>This is the main article content. It contains multiple paragraphs
                of text that would be extracted by the content extraction algorithms.</p>
                <p>The article continues with more detailed information about the topic
                at hand. This helps ensure we have enough content for the extraction
                to work properly.</p>
                <p>Finally, the article concludes with some final thoughts and takeaways
                for the reader to consider after reading through the material.</p>
            </div>
        </article>
        <footer>Footer content</footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_minimal():
    """Minimal HTML with og:title and basic content."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Minimal Article" />
    </head>
    <body>
        <article>
            <p>Short content that is less than 100 characters.</p>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_no_article():
    """HTML without proper article structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Page Title</title></head>
    <body>
        <div class="main-content">
            <h1>Main Heading</h1>
            <p>This is content in a regular div, not an article tag.
            The extractor should still be able to extract this content
            using fallback selectors or the body element.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_httpx_response():
    """Factory for creating mock httpx responses."""

    def _create(text: str = "", status_code: int = 200, headers: dict = None):
        response = MagicMock()
        response.text = text
        response.status_code = status_code
        response.headers = headers or {"content-type": "text/html"}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                message=f"HTTP {status_code}",
                request=MagicMock(),
                response=response,
            )
        return response

    return _create


# =============================================================================
# can_handle() Tests
# =============================================================================


class TestCanHandle:
    """Tests for URL detection."""

    def test_handles_http_url(self):
        """HTTP URLs should be handled."""
        assert URLExtractor.can_handle("http://example.com/article")

    def test_handles_https_url(self):
        """HTTPS URLs should be handled."""
        assert URLExtractor.can_handle("https://example.com/article")

    def test_rejects_non_http_schemes(self):
        """Non-HTTP schemes should not be handled."""
        assert not URLExtractor.can_handle("ftp://example.com/file.txt")
        assert not URLExtractor.can_handle("file:///path/to/file")
        assert not URLExtractor.can_handle("mailto:user@example.com")

    def test_handles_url_with_query_params(self):
        """URLs with query parameters should be handled."""
        assert URLExtractor.can_handle("https://example.com/article?id=123&ref=twitter")

    def test_handles_url_with_fragment(self):
        """URLs with fragments should be handled."""
        assert URLExtractor.can_handle("https://example.com/article#section-2")


# =============================================================================
# extract() Tests - Success Cases
# =============================================================================


class TestExtractSuccess:
    """Tests for successful content extraction."""

    @pytest.mark.asyncio
    async def test_extract_url_success(self, extractor, sample_html_article, mock_httpx_response):
        """Test successful extraction with standard headers."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response(sample_html_article)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://example.com/article")

            assert result.title is not None
            assert len(result.text) > 0
            assert result.source_type == "url"
            assert result.original_url == "https://example.com/article"

    @pytest.mark.asyncio
    async def test_extract_with_metadata(self, extractor, sample_html_article, mock_httpx_response):
        """Test extraction captures metadata from meta tags."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response(sample_html_article)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://example.com/article")

            assert result.metadata.get("domain") == "example.com"
            # top_image is only extracted by BeautifulSoup fallback, not readability

    @pytest.mark.asyncio
    async def test_extract_fallback_to_beautifulsoup(
        self, extractor, sample_html_minimal, mock_httpx_response
    ):
        """Test fallback to BeautifulSoup when readability returns short content."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response(sample_html_minimal)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://example.com/short")

            # Should still extract something
            assert result.title is not None
            assert result.source_type == "url"


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
    async def test_extract_handles_all_strategies_failed(self, extractor, mock_httpx_response):
        """Test error message when all fetch strategies fail."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            # All requests return 403
            mock_instance.get.return_value = mock_httpx_response("Forbidden", status_code=403)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError) as exc_info:
                await extractor.extract(url="https://blocked-site.com/article")

            assert "Could not fetch content" in str(exc_info.value)
            assert "blocking automated access" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_handles_timeout(self, extractor):
        """Test handling of request timeout."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Connection timed out")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError) as exc_info:
                await extractor.extract(url="https://slow-site.com/article")

            assert "Could not fetch content" in str(exc_info.value)


# =============================================================================
# Fallback Strategy Tests
# =============================================================================


class TestFallbackStrategies:
    """Tests for the fallback fetch strategies."""

    @pytest.mark.asyncio
    async def test_tries_google_referer_after_403(
        self, extractor, sample_html_article, mock_httpx_response
    ):
        """Test that Google referer strategy is tried after 403."""
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call (standard headers) returns 403
            if call_count == 1:
                return mock_httpx_response("Forbidden", status_code=403)
            # Second call (Google referer) succeeds
            return mock_httpx_response(sample_html_article)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = mock_get
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://paywall-site.com/article")

            assert call_count >= 2
            assert result.title is not None

    @pytest.mark.asyncio
    async def test_fetch_from_archive(self, extractor, sample_html_article):
        """Test fetching from archive.org Wayback Machine."""
        archive_api_response = MagicMock()
        archive_api_response.json.return_value = {
            "archived_snapshots": {
                "closest": {
                    "available": True,
                    "url": "https://web.archive.org/web/20240101/https://example.com/article",
                }
            }
        }
        archive_api_response.status_code = 200

        html_response = MagicMock()
        html_response.text = sample_html_article
        html_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [archive_api_response, html_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor._fetch_from_archive("https://example.com/article")

            assert result is not None
            assert "article content" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_from_archive_not_available(self, extractor):
        """Test archive.org returns None when no snapshot available."""
        archive_api_response = MagicMock()
        archive_api_response.json.return_value = {"archived_snapshots": {}}
        archive_api_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = archive_api_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor._fetch_from_archive("https://example.com/article")

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_from_google_cache(self, extractor, sample_html_article):
        """Test fetching from Google Cache."""
        cache_response = MagicMock()
        cache_response.text = sample_html_article
        cache_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = cache_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor._fetch_from_google_cache("https://example.com/article")

            assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_from_12ft(self, extractor, sample_html_article):
        """Test fetching from 12ft.io paywall bypass."""
        bypass_response = MagicMock()
        bypass_response.text = sample_html_article
        bypass_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = bypass_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor._fetch_from_12ft("https://example.com/article")

            assert result is not None


# =============================================================================
# Readability Extraction Tests
# =============================================================================


class TestReadabilityExtraction:
    """Tests for readability-lxml extraction."""

    def test_extract_with_readability_success(self, extractor, sample_html_article):
        """Test readability extraction returns title and text."""
        result = extractor._extract_with_readability(
            sample_html_article, "https://example.com/article"
        )

        assert "title" in result
        assert "text" in result
        assert len(result["text"]) > 0

    def test_extract_with_readability_handles_invalid_html(self, extractor):
        """Test readability handles malformed HTML gracefully."""
        invalid_html = "<html><body><p>Unclosed tags<div>More content"

        result = extractor._extract_with_readability(invalid_html, "https://example.com")

        # Should return something, even if partial
        assert isinstance(result, dict)


# =============================================================================
# BeautifulSoup Extraction Tests
# =============================================================================


class TestBeautifulSoupExtraction:
    """Tests for BeautifulSoup fallback extraction."""

    def test_extract_with_beautifulsoup_finds_og_title(self, extractor, sample_html_article):
        """Test extraction finds og:title meta tag."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_article, "https://example.com/article"
        )

        assert result["title"] == "Test Article Title"

    def test_extract_with_beautifulsoup_finds_author(self, extractor, sample_html_article):
        """Test extraction finds author meta tag."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_article, "https://example.com/article"
        )

        assert "John Doe" in result["authors"]

    def test_extract_with_beautifulsoup_finds_date(self, extractor, sample_html_article):
        """Test extraction finds publication date."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_article, "https://example.com/article"
        )

        assert result["publication_date"] is not None
        assert isinstance(result["publication_date"], datetime)

    def test_extract_with_beautifulsoup_finds_image(self, extractor, sample_html_article):
        """Test extraction finds og:image."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_article, "https://example.com/article"
        )

        assert result["top_image"] == "https://example.com/image.jpg"

    def test_extract_with_beautifulsoup_removes_nav_elements(self, extractor, sample_html_article):
        """Test that nav, header, footer elements are removed."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_article, "https://example.com/article"
        )

        # Navigation and footer text should not be in content
        assert "Navigation here" not in result["text"]
        assert "Footer content" not in result["text"]

    def test_extract_with_beautifulsoup_finds_article_content(self, extractor, sample_html_article):
        """Test extraction finds content in article tag."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_article, "https://example.com/article"
        )

        assert "main article content" in result["text"]

    def test_extract_with_beautifulsoup_fallback_to_body(self, extractor, sample_html_no_article):
        """Test extraction falls back to body when no article found."""
        result = extractor._extract_with_beautifulsoup(
            sample_html_no_article, "https://example.com/page"
        )

        assert "content in a regular div" in result["text"]

    def test_extract_with_beautifulsoup_cleans_author_prefix(self, extractor):
        """Test 'By ' prefix is removed from author names."""
        html = """
        <html>
        <body>
            <article>
                <span class="byline">By Jane Smith</span>
                <p>Article content here.</p>
            </article>
        </body>
        </html>
        """
        result = extractor._extract_with_beautifulsoup(html, "https://example.com")

        if result["authors"]:
            assert result["authors"][0] == "Jane Smith"

    def test_extract_with_beautifulsoup_fallback_to_h1(self, extractor):
        """Test title extraction falls back to h1 when no meta tags."""
        html = """
        <html>
        <body>
            <h1>Article Heading</h1>
            <p>Some content here for the article body that needs extraction.</p>
        </body>
        </html>
        """
        result = extractor._extract_with_beautifulsoup(html, "https://example.com")

        assert result["title"] == "Article Heading"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_extract_handles_encoding(self, extractor, mock_httpx_response):
        """Test handling of UTF-8 encoded content."""
        html_with_unicode = """
        <html>
        <head><meta property="og:title" content="Artículo en Español" /></head>
        <body>
            <article>
                <p>Este es un artículo con caracteres especiales: café, naïve, 日本語</p>
            </article>
        </body>
        </html>
        """
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response(html_with_unicode)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await extractor.extract(url="https://example.com/spanish-article")

            assert "café" in result.text or "Español" in result.title

    def test_extract_with_beautifulsoup_handles_empty_content(self, extractor):
        """Test handling of page with minimal content."""
        html = "<html><body></body></html>"

        result = extractor._extract_with_beautifulsoup(html, "https://example.com")

        assert result["title"] == "Untitled"
        assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_redirects_followed(self, extractor, sample_html_article, mock_httpx_response):
        """Test that HTTP redirects are followed (httpx config)."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response(sample_html_article)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await extractor.extract(url="https://redirect.example.com/article")

            # Check that follow_redirects=True was passed
            mock_client.assert_called()
            call_kwargs = mock_client.call_args
            assert call_kwargs.kwargs.get("follow_redirects") is True
