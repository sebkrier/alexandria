"""
Tests for the Substack extractor (app/extractors/substack.py).

Tests Substack URL detection, curl-based fetching (to bypass Cloudflare),
and content extraction from Substack's HTML structure.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.extractors.substack import SubstackExtractor


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def extractor():
    """Create a SubstackExtractor instance."""
    return SubstackExtractor()


@pytest.fixture
def sample_substack_html():
    """Sample Substack article HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>My Newsletter Post - by John Author</title>
        <meta property="og:title" content="My Newsletter Post" />
        <meta name="author" content="John Author" />
    </head>
    <body>
        <article>
            <h1 class="post-title">My Newsletter Post</h1>
            <h3 class="subtitle">A thought-provoking subtitle</h3>
            <a class="frontend-pencraft-Text-module__decoration-hover-underline--BEYAn">John Author</a>
            <time datetime="2024-03-15T10:00:00Z">March 15, 2024</time>
            <div class="body">
                <p>This is the main content of the Substack newsletter post.</p>
                <p>It contains multiple paragraphs of insightful commentary.</p>
                <p>Readers find this content valuable and engaging.</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_substack_html_minimal():
    """Minimal Substack HTML without all elements."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simple Post</title>
    </head>
    <body>
        <article>
            <h1>Simple Post Title</h1>
            <div class="post-content">
                <p>Simple post content here.</p>
            </div>
        </article>
    </body>
    </html>
    """


# =============================================================================
# can_handle() Tests
# =============================================================================


class TestCanHandle:
    """Tests for Substack URL detection."""

    def test_handles_substack_domain(self):
        """Direct substack.com URLs should be handled."""
        assert SubstackExtractor.can_handle("https://example.substack.com/p/my-post")
        assert SubstackExtractor.can_handle("https://www.substack.com/newsletter")

    def test_handles_custom_domain_with_p_path(self):
        """Custom domains with /p/ path pattern should be handled."""
        assert SubstackExtractor.can_handle("https://newsletter.example.com/p/article-slug")

    def test_rejects_non_substack_urls(self):
        """Non-Substack URLs without /p/ pattern should not be handled."""
        assert not SubstackExtractor.can_handle("https://example.com/article")
        assert not SubstackExtractor.can_handle("https://example.com/blog/post")
        # Note: /p/ pattern matches on any domain (custom Substack domains)

    def test_rejects_substack_home_page(self):
        """Substack home pages without /p/ should not be handled (unless on substack.com)."""
        # On substack.com domain, any path is handled
        assert SubstackExtractor.can_handle("https://test.substack.com/")
        # Custom domain needs /p/ pattern
        assert not SubstackExtractor.can_handle("https://example.com/about")


# =============================================================================
# extract() Tests - Success Cases
# =============================================================================


class TestExtractSuccess:
    """Tests for successful Substack extraction."""

    @pytest.mark.asyncio
    async def test_extract_substack_article(self, extractor, sample_substack_html):
        """Test extracting a standard Substack article."""
        with patch.object(extractor, "_fetch_html", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_substack_html

            result = await extractor.extract(url="https://example.substack.com/p/my-post")

            assert result.title == "My Newsletter Post"
            assert "main content" in result.text
            assert result.source_type == "url"

    @pytest.mark.asyncio
    async def test_extract_with_authors(self, extractor, sample_substack_html):
        """Test author extraction from Substack."""
        with patch.object(extractor, "_fetch_html", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_substack_html

            result = await extractor.extract(url="https://example.substack.com/p/my-post")

            assert len(result.authors) > 0
            assert "John Author" in result.authors

    @pytest.mark.asyncio
    async def test_extract_with_publication_date(self, extractor, sample_substack_html):
        """Test publication date extraction."""
        with patch.object(extractor, "_fetch_html", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_substack_html

            result = await extractor.extract(url="https://example.substack.com/p/my-post")

            assert result.publication_date is not None
            assert isinstance(result.publication_date, datetime)
            # Should be timezone-naive (stripped for database)
            assert result.publication_date.tzinfo is None

    @pytest.mark.asyncio
    async def test_extract_with_subtitle(self, extractor, sample_substack_html):
        """Test subtitle is captured in metadata."""
        with patch.object(extractor, "_fetch_html", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_substack_html

            result = await extractor.extract(url="https://example.substack.com/p/my-post")

            assert result.metadata.get("subtitle") == "A thought-provoking subtitle"


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
    async def test_extract_handles_fetch_failure(self, extractor):
        """Test handling of curl fetch failure."""
        with patch.object(extractor, "_fetch_html", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Failed to fetch URL: connection refused")

            with pytest.raises(RuntimeError, match="Failed to fetch"):
                await extractor.extract(url="https://example.substack.com/p/my-post")


# =============================================================================
# _fetch_html() Tests
# =============================================================================


class TestFetchHtml:
    """Tests for curl-based HTML fetching."""

    @pytest.mark.asyncio
    async def test_fetch_uses_curl(self, extractor):
        """Test that fetch uses curl subprocess."""
        # Response needs to be > 100 chars to pass validation
        long_content = b"<html><body>" + b"Content here. " * 20 + b"</body></html>"
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(long_content, b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await extractor._fetch_html("https://example.substack.com/p/post")

            # Verify curl was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            # First positional arg should be "curl"
            assert call_args[0][0] == "curl"
            # Check that silent and follow-redirect flags are present
            assert "-s" in call_args[0]
            assert "-L" in call_args[0]

    @pytest.mark.asyncio
    async def test_fetch_handles_curl_error(self, extractor):
        """Test handling of curl command failure."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Connection refused")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError, match="Failed to fetch URL"):
                await extractor._fetch_html("https://example.substack.com/p/post")

    @pytest.mark.asyncio
    async def test_fetch_handles_empty_response(self, extractor):
        """Test handling of empty response from curl."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError, match="Empty or invalid response"):
                await extractor._fetch_html("https://example.substack.com/p/post")


# =============================================================================
# _extract_content() Tests
# =============================================================================


class TestExtractContent:
    """Tests for HTML content extraction."""

    def test_finds_og_title(self, extractor, sample_substack_html):
        """Test title extraction from og:title meta tag."""
        result = extractor._extract_content(sample_substack_html, "https://example.com")

        assert result["title"] == "My Newsletter Post"

    def test_finds_post_title_class(self, extractor):
        """Test title extraction from post-title class."""
        html = """
        <html>
        <head></head>
        <body>
            <h1 class="post-title">Post Title From Class</h1>
            <div class="body"><p>Content here.</p></div>
        </body>
        </html>
        """
        result = extractor._extract_content(html, "https://example.com")

        assert result["title"] == "Post Title From Class"

    def test_strips_author_from_title_tag(self, extractor):
        """Test that ' - by Author' suffix is removed from title."""
        html = """
        <html>
        <head><title>My Post - by John Smith</title></head>
        <body>
            <div class="body"><p>Content here.</p></div>
        </body>
        </html>
        """
        result = extractor._extract_content(html, "https://example.com")

        assert result["title"] == "My Post"

    def test_finds_author_from_meta(self, extractor):
        """Test author extraction from meta tag."""
        html = """
        <html>
        <head><meta name="author" content="Jane Doe" /></head>
        <body>
            <h1>Post</h1>
            <div class="body"><p>Content.</p></div>
        </body>
        </html>
        """
        result = extractor._extract_content(html, "https://example.com")

        assert "Jane Doe" in result["authors"]

    def test_removes_subscribe_prompts(self, extractor):
        """Test that subscribe/paywall prompts are removed."""
        html = """
        <html>
        <body>
            <article>
                <div class="body">
                    <p>Main article content here.</p>
                    <div class="subscribe-prompt">Subscribe to read more!</div>
                    <div class="paywall-message">This is behind a paywall.</div>
                </div>
            </article>
        </body>
        </html>
        """
        result = extractor._extract_content(html, "https://example.com")

        assert "Subscribe to read more" not in result["text"]
        assert "paywall" not in result["text"].lower()

    def test_removes_script_and_style(self, extractor):
        """Test that script and style elements are removed."""
        html = """
        <html>
        <body>
            <article>
                <div class="body">
                    <p>Visible content.</p>
                    <script>alert('hidden');</script>
                    <style>.hidden { display: none; }</style>
                </div>
            </article>
        </body>
        </html>
        """
        result = extractor._extract_content(html, "https://example.com")

        assert "alert" not in result["text"]
        assert "display: none" not in result["text"]

    def test_handles_missing_content(self, extractor):
        """Test handling of page with minimal content."""
        html = "<html><body></body></html>"
        result = extractor._extract_content(html, "https://example.com")

        assert result["title"] == "Untitled"
        assert result["text"] == ""


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_handles_utf8_encoding(self, extractor):
        """Test handling of UTF-8 encoded content."""
        html = """
        <html>
        <head><meta property="og:title" content="日本語タイトル" /></head>
        <body>
            <div class="body">
                <p>Content with émojis 🎉 and spëcial characters.</p>
            </div>
        </body>
        </html>
        """
        with patch.object(extractor, "_fetch_html", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html

            result = await extractor.extract(url="https://example.substack.com/p/post")

            assert "🎉" in result.text or "émojis" in result.text

    def test_content_selector_fallback_order(self, extractor):
        """Test content selector fallback: body -> post-content -> article -> body."""
        # Test with .body class
        html1 = '<html><body><div class="body"><p>Body class content.</p></div></body></html>'
        result1 = extractor._extract_content(html1, "https://example.com")
        assert "Body class content" in result1["text"]

        # Test fallback to .post-content
        html2 = '<html><body><div class="post-content"><p>Post content.</p></div></body></html>'
        result2 = extractor._extract_content(html2, "https://example.com")
        assert "Post content" in result2["text"]

        # Test fallback to article
        html3 = "<html><body><article><p>Article content.</p></article></body></html>"
        result3 = extractor._extract_content(html3, "https://example.com")
        assert "Article content" in result3["text"]
