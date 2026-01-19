"""
Tests for extractor routing module (app/extractors/__init__.py).

Tests content-type detection, extractor selection, and fallback logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.extractors import (
    EXTRACTORS,
    ArxivExtractor,
    ExtractedContent,
    LessWrongExtractor,
    PDFExtractor,
    SubstackExtractor,
    URLExtractor,
    YouTubeExtractor,
    _detect_content_type,
    extract_content,
)

# =============================================================================
# Content-Type Detection Tests
# =============================================================================


class TestDetectContentType:
    """Tests for _detect_content_type() function."""

    @pytest.mark.asyncio
    async def test_detect_content_type_success(self):
        """Test successful content-type detection via HEAD request."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.headers = {"content-type": "application/pdf; charset=utf-8"}
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _detect_content_type("https://example.com/document.pdf")

            assert result == "application/pdf; charset=utf-8"
            mock_client.head.assert_called_once_with("https://example.com/document.pdf")

    @pytest.mark.asyncio
    async def test_detect_content_type_html(self):
        """Test content-type detection returns HTML."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.headers = {"content-type": "text/html; charset=UTF-8"}
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _detect_content_type("https://example.com/article")

            assert result == "text/html; charset=utf-8"

    @pytest.mark.asyncio
    async def test_detect_content_type_missing_header(self):
        """Test content-type detection when header is missing."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.headers = {}  # No content-type header
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _detect_content_type("https://example.com/unknown")

            assert result == ""

    @pytest.mark.asyncio
    async def test_detect_content_type_failure_returns_none(self):
        """Test content-type detection returns None on HTTP error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _detect_content_type("https://unreachable.com/doc")

            assert result is None

    @pytest.mark.asyncio
    async def test_detect_content_type_timeout(self):
        """Test content-type detection returns None on timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _detect_content_type("https://slow-server.com/doc")

            assert result is None


# =============================================================================
# Extractor Selection Tests
# =============================================================================


class TestExtractorSelection:
    """Tests for extractor selection via can_handle()."""

    def test_extractors_list_order(self):
        """Test EXTRACTORS list has correct order (specific before generic)."""
        # Verify specific extractors come before generic URLExtractor
        extractor_names = [e.__name__ for e in EXTRACTORS]

        # URLExtractor should be last (fallback)
        assert extractor_names[-1] == "URLExtractor"

        # Specific extractors should be before generic
        assert extractor_names.index("ArxivExtractor") < extractor_names.index("URLExtractor")
        assert extractor_names.index("YouTubeExtractor") < extractor_names.index("URLExtractor")
        assert extractor_names.index("PDFExtractor") < extractor_names.index("URLExtractor")

    def test_arxiv_can_handle(self):
        """Test ArxivExtractor can_handle detection."""
        assert ArxivExtractor.can_handle("https://arxiv.org/abs/2301.00001") is True
        assert ArxivExtractor.can_handle("https://example.com/article") is False

    def test_youtube_can_handle(self):
        """Test YouTubeExtractor can_handle detection."""
        assert YouTubeExtractor.can_handle("https://www.youtube.com/watch?v=abc123") is True
        assert YouTubeExtractor.can_handle("https://youtu.be/abc123") is True
        assert YouTubeExtractor.can_handle("https://example.com/video") is False

    def test_pdf_can_handle(self):
        """Test PDFExtractor can_handle detection."""
        assert PDFExtractor.can_handle("https://example.com/paper.pdf") is True
        assert PDFExtractor.can_handle("https://example.com/article") is False

    def test_substack_can_handle(self):
        """Test SubstackExtractor can_handle detection."""
        assert SubstackExtractor.can_handle("https://example.substack.com/p/article") is True
        assert SubstackExtractor.can_handle("https://example.com/article") is False

    def test_lesswrong_can_handle(self):
        """Test LessWrongExtractor can_handle detection."""
        assert LessWrongExtractor.can_handle("https://www.lesswrong.com/posts/abc123/post-slug") is True
        assert LessWrongExtractor.can_handle("https://www.alignmentforum.org/posts/abc123/post-slug") is True
        assert LessWrongExtractor.can_handle("https://example.com/post") is False


# =============================================================================
# extract_content() Tests
# =============================================================================


class TestExtractContent:
    """Tests for the main extract_content() function."""

    @pytest.mark.asyncio
    async def test_extract_content_no_url_or_path_raises(self):
        """Test extract_content raises ValueError when no URL or path provided."""
        with pytest.raises(ValueError, match="Either url or file_path must be provided"):
            await extract_content()

    @pytest.mark.asyncio
    async def test_extract_content_file_path_uses_pdf_extractor(self):
        """Test file_path routes to PDFExtractor."""
        mock_content = ExtractedContent(
            title="Test PDF",
            text="PDF content here",
            source_type="pdf",
        )

        with patch.object(PDFExtractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_content

            result = await extract_content(file_path="/path/to/document.pdf")

            mock_extract.assert_called_once_with(file_path="/path/to/document.pdf")
            assert result.title == "Test PDF"

    @pytest.mark.asyncio
    async def test_extract_content_youtube_url(self):
        """Test YouTube URL routes to YouTubeExtractor."""
        mock_content = ExtractedContent(
            title="Test Video",
            text="Video transcript",
            source_type="youtube",
        )

        with patch.object(YouTubeExtractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://www.youtube.com/watch?v=abc123")

            mock_extract.assert_called_once()
            assert result.title == "Test Video"

    @pytest.mark.asyncio
    async def test_extract_content_arxiv_url(self):
        """Test arXiv URL routes to ArxivExtractor."""
        mock_content = ExtractedContent(
            title="Research Paper",
            text="Abstract and content",
            source_type="arxiv",
        )

        with patch.object(ArxivExtractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://arxiv.org/abs/2301.00001")

            mock_extract.assert_called_once()
            assert result.title == "Research Paper"

    @pytest.mark.asyncio
    async def test_extract_content_pdf_url(self):
        """Test PDF URL routes to PDFExtractor."""
        mock_content = ExtractedContent(
            title="PDF Document",
            text="PDF text content",
            source_type="pdf",
        )

        with patch.object(PDFExtractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://example.com/paper.pdf")

            mock_extract.assert_called_once()
            assert result.title == "PDF Document"

    @pytest.mark.asyncio
    async def test_extract_content_extractor_failure_triggers_content_type_detection(self):
        """Test that when an extractor fails, content-type detection is triggered."""
        mock_content = ExtractedContent(
            title="Fallback Content",
            text="Content from fallback",
            source_type="url",
        )

        with (
            patch.object(
                ArxivExtractor, "extract", new_callable=AsyncMock, side_effect=Exception("Extraction failed")
            ),
            patch(
                "app.extractors._detect_content_type", new_callable=AsyncMock, return_value="text/html"
            ) as mock_detect,
            patch.object(URLExtractor, "extract", new_callable=AsyncMock) as mock_url_extract,
        ):
            mock_url_extract.return_value = mock_content

            result = await extract_content(url="https://arxiv.org/abs/2301.00001")

            # Content-type detection should be called after extractor failure
            mock_detect.assert_called_once_with("https://arxiv.org/abs/2301.00001")
            # Should fallback to URLExtractor based on HTML content-type
            assert result.title == "Fallback Content"

    @pytest.mark.asyncio
    async def test_extract_content_pdf_by_content_type(self):
        """Test PDF detected by content-type (not URL extension)."""
        mock_content = ExtractedContent(
            title="PDF from Content-Type",
            text="Content detected as PDF",
            source_type="pdf",
        )

        with (
            # No extractor matches the URL pattern
            patch.object(ArxivExtractor, "can_handle", return_value=False),
            patch.object(SubstackExtractor, "can_handle", return_value=False),
            patch.object(YouTubeExtractor, "can_handle", return_value=False),
            patch.object(LessWrongExtractor, "can_handle", return_value=False),
            patch.object(PDFExtractor, "can_handle", return_value=False),
            patch.object(URLExtractor, "can_handle", return_value=False),
            # Content-type detection returns PDF
            patch(
                "app.extractors._detect_content_type",
                new_callable=AsyncMock,
                return_value="application/pdf",
            ),
            patch.object(PDFExtractor, "extract", new_callable=AsyncMock) as mock_extract,
        ):
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://example.com/download?id=123")

            mock_extract.assert_called_once()
            assert result.title == "PDF from Content-Type"

    @pytest.mark.asyncio
    async def test_extract_content_html_by_content_type(self):
        """Test HTML detected by content-type triggers URLExtractor."""
        mock_content = ExtractedContent(
            title="HTML Article",
            text="Article content",
            source_type="url",
        )

        with (
            # No extractor matches the URL pattern
            patch.object(ArxivExtractor, "can_handle", return_value=False),
            patch.object(SubstackExtractor, "can_handle", return_value=False),
            patch.object(YouTubeExtractor, "can_handle", return_value=False),
            patch.object(LessWrongExtractor, "can_handle", return_value=False),
            patch.object(PDFExtractor, "can_handle", return_value=False),
            patch.object(URLExtractor, "can_handle", return_value=False),
            # Content-type detection returns HTML
            patch(
                "app.extractors._detect_content_type",
                new_callable=AsyncMock,
                return_value="text/html; charset=utf-8",
            ),
            patch.object(URLExtractor, "extract", new_callable=AsyncMock) as mock_extract,
        ):
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://example.com/article")

            mock_extract.assert_called_once()
            assert result.title == "HTML Article"

    @pytest.mark.asyncio
    async def test_extract_content_text_plain_by_content_type(self):
        """Test text/plain content-type triggers URLExtractor."""
        mock_content = ExtractedContent(
            title="Plain Text",
            text="Plain text content",
            source_type="url",
        )

        with (
            # No extractor matches
            patch.object(ArxivExtractor, "can_handle", return_value=False),
            patch.object(SubstackExtractor, "can_handle", return_value=False),
            patch.object(YouTubeExtractor, "can_handle", return_value=False),
            patch.object(LessWrongExtractor, "can_handle", return_value=False),
            patch.object(PDFExtractor, "can_handle", return_value=False),
            patch.object(URLExtractor, "can_handle", return_value=False),
            # Content-type is text/plain
            patch(
                "app.extractors._detect_content_type",
                new_callable=AsyncMock,
                return_value="text/plain",
            ),
            patch.object(URLExtractor, "extract", new_callable=AsyncMock) as mock_extract,
        ):
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://example.com/plain.txt")

            mock_extract.assert_called_once()
            assert result.title == "Plain Text"

    @pytest.mark.asyncio
    async def test_extract_content_final_fallback_to_url_extractor(self):
        """Test final fallback to URLExtractor when content-type detection fails."""
        mock_content = ExtractedContent(
            title="Fallback Article",
            text="Extracted via fallback",
            source_type="url",
        )

        with (
            # No extractor matches
            patch.object(ArxivExtractor, "can_handle", return_value=False),
            patch.object(SubstackExtractor, "can_handle", return_value=False),
            patch.object(YouTubeExtractor, "can_handle", return_value=False),
            patch.object(LessWrongExtractor, "can_handle", return_value=False),
            patch.object(PDFExtractor, "can_handle", return_value=False),
            patch.object(URLExtractor, "can_handle", return_value=False),
            # Content-type detection returns None (failed)
            patch(
                "app.extractors._detect_content_type",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(URLExtractor, "extract", new_callable=AsyncMock) as mock_extract,
        ):
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://mysterious-server.com/content")

            mock_extract.assert_called_once()
            assert result.title == "Fallback Article"

    @pytest.mark.asyncio
    async def test_extract_content_unknown_content_type_uses_fallback(self):
        """Test unknown content-type falls back to URLExtractor."""
        mock_content = ExtractedContent(
            title="Unknown Type",
            text="Content with unknown type",
            source_type="url",
        )

        with (
            # No extractor matches
            patch.object(ArxivExtractor, "can_handle", return_value=False),
            patch.object(SubstackExtractor, "can_handle", return_value=False),
            patch.object(YouTubeExtractor, "can_handle", return_value=False),
            patch.object(LessWrongExtractor, "can_handle", return_value=False),
            patch.object(PDFExtractor, "can_handle", return_value=False),
            patch.object(URLExtractor, "can_handle", return_value=False),
            # Content-type is something unusual
            patch(
                "app.extractors._detect_content_type",
                new_callable=AsyncMock,
                return_value="application/octet-stream",
            ),
            patch.object(URLExtractor, "extract", new_callable=AsyncMock) as mock_extract,
        ):
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://example.com/binary")

            mock_extract.assert_called_once()
            assert result.title == "Unknown Type"

    @pytest.mark.asyncio
    async def test_extract_content_substack_url(self):
        """Test Substack URL routes to SubstackExtractor."""
        mock_content = ExtractedContent(
            title="Substack Post",
            text="Newsletter content",
            source_type="url",
        )

        with patch.object(SubstackExtractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://example.substack.com/p/my-post")

            mock_extract.assert_called_once()
            assert result.title == "Substack Post"

    @pytest.mark.asyncio
    async def test_extract_content_lesswrong_url(self):
        """Test LessWrong URL routes to LessWrongExtractor."""
        mock_content = ExtractedContent(
            title="LessWrong Post",
            text="Rationalist content",
            source_type="url",
        )

        with patch.object(LessWrongExtractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_content

            result = await extract_content(url="https://www.lesswrong.com/posts/abc123/my-post")

            mock_extract.assert_called_once()
            assert result.title == "LessWrong Post"
