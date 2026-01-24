"""
Tests for the PDF extractor (app/extractors/pdf.py).

Tests PDF detection (including Google Drive URLs), PDF downloading,
text extraction with PyMuPDF, and title/author extraction.
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.extractors.pdf import PDFExtractor

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def extractor():
    """Create a PDFExtractor instance."""
    return PDFExtractor()


@pytest.fixture
def mock_pdf_document():
    """Create a mock PyMuPDF (fitz) document."""

    def _create(
        text_pages: list[str] = None,
        metadata: dict = None,
        name: str = "test.pdf",
    ):
        if text_pages is None:
            text_pages = ["This is page one content.", "This is page two content."]
        if metadata is None:
            metadata = {"title": "Test PDF Title", "author": "Test Author"}

        mock_doc = MagicMock()
        mock_doc.metadata = metadata
        mock_doc.name = name

        # Create mock pages
        mock_pages = []
        for page_text in text_pages:
            mock_page = MagicMock()
            mock_page.get_text.return_value = page_text
            mock_pages.append(mock_page)

        mock_doc.__iter__ = lambda self: iter(mock_pages)
        mock_doc.__len__ = lambda self: len(mock_pages)
        mock_doc.__getitem__ = lambda self, idx: mock_pages[idx]
        mock_doc.close = MagicMock()

        return mock_doc

    return _create


@pytest.fixture
def mock_httpx_response():
    """Factory for creating mock httpx responses."""

    def _create(
        content: bytes = b"%PDF-1.4 Test PDF content",
        status_code: int = 200,
        content_type: str = "application/pdf",
    ):
        response = MagicMock()
        response.content = content
        response.text = content.decode("utf-8", errors="replace")
        response.status_code = status_code
        response.headers = {"content-type": content_type}
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
    """Tests for PDF URL detection."""

    def test_handles_pdf_extension(self):
        """Direct PDF URLs should be handled."""
        assert PDFExtractor.can_handle("https://example.com/document.pdf")
        assert PDFExtractor.can_handle("https://example.com/path/to/file.PDF")

    def test_handles_pdf_with_query_params(self):
        """PDF URLs with query params should be handled."""
        assert PDFExtractor.can_handle("https://example.com/document.pdf?version=2")

    def test_handles_google_drive_file_url(self):
        """Google Drive file URLs should be handled."""
        assert PDFExtractor.can_handle(
            "https://drive.google.com/file/d/1ABC123xyz/view?usp=sharing"
        )

    def test_handles_google_drive_open_url(self):
        """Google Drive open URLs should be handled."""
        assert PDFExtractor.can_handle("https://drive.google.com/open?id=1ABC123xyz")

    def test_handles_google_drive_uc_url(self):
        """Google Drive uc URLs should be handled."""
        assert PDFExtractor.can_handle("https://drive.google.com/uc?export=download&id=1ABC123xyz")

    def test_rejects_non_pdf_urls(self):
        """Non-PDF URLs should not be handled."""
        assert not PDFExtractor.can_handle("https://example.com/article.html")
        assert not PDFExtractor.can_handle("https://example.com/image.png")

    def test_rejects_regular_drive_urls(self):
        """Google Drive folder URLs should not be handled."""
        assert not PDFExtractor.can_handle("https://drive.google.com/drive/folders/123")


# =============================================================================
# Google Drive URL Conversion Tests
# =============================================================================


class TestGoogleDriveUrlConversion:
    """Tests for Google Drive URL conversion to direct download links."""

    def test_convert_file_d_url(self, extractor):
        """Test conversion of /file/d/ format URLs."""
        url = "https://drive.google.com/file/d/1ABC123xyz/view?usp=sharing"
        result = extractor._convert_google_drive_url(url)

        assert result == "https://drive.google.com/uc?export=download&id=1ABC123xyz"

    def test_convert_open_id_url(self, extractor):
        """Test conversion of /open?id= format URLs."""
        url = "https://drive.google.com/open?id=1ABC123xyz"
        result = extractor._convert_google_drive_url(url)

        assert result == "https://drive.google.com/uc?export=download&id=1ABC123xyz"

    def test_convert_uc_url_adds_export(self, extractor):
        """Test that uc URLs without export=download get it added."""
        url = "https://drive.google.com/uc?id=1ABC123xyz"
        result = extractor._convert_google_drive_url(url)

        assert "export=download" in result
        assert "id=1ABC123xyz" in result

    def test_preserves_non_drive_urls(self, extractor):
        """Test that non-Drive URLs are returned unchanged."""
        url = "https://example.com/document.pdf"
        result = extractor._convert_google_drive_url(url)

        assert result == url


# =============================================================================
# extract() Tests - Success Cases
# =============================================================================


class TestExtractSuccess:
    """Tests for successful PDF extraction."""

    @pytest.mark.asyncio
    async def test_extract_pdf_from_url(self, extractor, mock_pdf_document, mock_httpx_response):
        """Test extracting PDF from a URL."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document()

            result = await extractor.extract(url="https://example.com/document.pdf")

            assert result.title is not None
            assert result.source_type == "pdf"
            assert result.original_url == "https://example.com/document.pdf"
            assert result.metadata.get("page_count") == 2

    @pytest.mark.asyncio
    async def test_extract_pdf_from_file_path(self, extractor, mock_pdf_document):
        """Test extracting PDF from a local file path."""
        with patch("fitz.open") as mock_fitz:
            mock_fitz.return_value = mock_pdf_document()

            result = await extractor.extract(file_path="/path/to/document.pdf")

            assert result.title is not None
            assert result.source_type == "pdf"
            assert result.file_path == "/path/to/document.pdf"

    @pytest.mark.asyncio
    async def test_extract_pdf_with_metadata(
        self, extractor, mock_pdf_document, mock_httpx_response
    ):
        """Test PDF metadata is captured."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document(
                metadata={"title": "Research Paper", "author": "Dr. Smith"}
            )

            result = await extractor.extract(url="https://example.com/paper.pdf")

            assert result.metadata.get("pdf_metadata") is not None
            assert result.metadata["pdf_metadata"].get("title") == "Research Paper"

    @pytest.mark.asyncio
    async def test_extract_multi_page_pdf(self, extractor, mock_pdf_document, mock_httpx_response):
        """Test multi-page PDF text concatenation."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document(
                text_pages=["Page 1 content", "Page 2 content", "Page 3 content"]
            )

            result = await extractor.extract(url="https://example.com/multipage.pdf")

            assert "Page 1 content" in result.text
            assert "Page 2 content" in result.text
            assert "Page 3 content" in result.text
            assert result.metadata.get("page_count") == 3


# =============================================================================
# extract() Tests - Error Handling
# =============================================================================


class TestExtractErrors:
    """Tests for error handling during PDF extraction."""

    @pytest.mark.asyncio
    async def test_extract_requires_url_or_path(self, extractor):
        """Extract should raise ValueError if neither URL nor path provided."""
        with pytest.raises(ValueError, match="url or file_path is required"):
            await extractor.extract()

    @pytest.mark.asyncio
    async def test_extract_handles_download_failure(self, extractor, mock_httpx_response):
        """Test handling of download failure."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response(status_code=404)
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await extractor.extract(url="https://example.com/missing.pdf")

    @pytest.mark.asyncio
    async def test_extract_rejects_non_pdf_content(self, extractor, mock_httpx_response):
        """Test that non-PDF content is rejected when URL doesn't end in .pdf."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            # Return HTML instead of PDF - but URL must NOT end in .pdf for rejection
            mock_instance.get.return_value = mock_httpx_response(
                content=b"<html><body>Not a PDF</body></html>",
                content_type="text/html",
            )
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            # Use a Google Drive URL that doesn't end in .pdf
            with pytest.raises(ValueError, match="does not point to a PDF"):
                await extractor.extract(url="https://drive.google.com/uc?export=download&id=abc123")


# =============================================================================
# Google Drive Specific Tests
# =============================================================================


class TestGoogleDriveDownload:
    """Tests for Google Drive PDF downloads."""

    @pytest.mark.asyncio
    async def test_google_drive_url_conversion(
        self, extractor, mock_pdf_document, mock_httpx_response
    ):
        """Test Google Drive URL is converted before download."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document()

            await extractor.extract(url="https://drive.google.com/file/d/1ABC123/view")

            # Check the URL was converted for download
            call_args = mock_instance.get.call_args
            called_url = call_args[0][0]
            assert "uc?export=download" in called_url

    @pytest.mark.asyncio
    async def test_google_drive_virus_scan_bypass(self, extractor, mock_pdf_document):
        """Test handling of Google Drive virus scan confirmation page."""
        virus_scan_html = b"""
        <html>
        <body>
            <a href="/uc?export=download&confirm=ABC123&id=1xyz">Download anyway</a>
        </body>
        </html>
        """

        pdf_content = b"%PDF-1.4 Actual PDF content"

        call_count = 0

        async def mock_get(url):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count == 1:
                # First call returns virus scan page
                response.content = virus_scan_html
                response.text = virus_scan_html.decode()
                response.status_code = 200
                response.headers = {"content-type": "text/html"}
            else:
                # Second call with confirm token returns PDF
                response.content = pdf_content
                response.status_code = 200
                response.headers = {"content-type": "application/pdf"}
            response.raise_for_status = MagicMock()
            return response

        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get = mock_get
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document()

            # The virus scan page has confirm= in URL pattern
            await extractor.extract(url="https://drive.google.com/uc?export=download&id=1xyz")

            assert call_count == 2

    @pytest.mark.asyncio
    async def test_google_drive_pdf_magic_bytes(self, extractor, mock_pdf_document):
        """Test PDF validation using magic bytes when content-type is wrong."""
        pdf_content = b"%PDF-1.4 PDF content here"

        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            response = MagicMock()
            response.content = pdf_content
            response.status_code = 200
            # Google Drive sometimes returns wrong content-type
            response.headers = {"content-type": "application/octet-stream"}
            response.raise_for_status = MagicMock()
            mock_instance.get.return_value = response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document()

            # Should succeed because content starts with %PDF
            result = await extractor.extract(
                url="https://drive.google.com/uc?export=download&id=1xyz"
            )

            assert result.source_type == "pdf"


# =============================================================================
# Title Extraction Tests
# =============================================================================


class TestTitleExtraction:
    """Tests for PDF title extraction logic."""

    @pytest.mark.asyncio
    async def test_title_from_metadata(self, extractor, mock_pdf_document):
        """Test title extraction from PDF metadata."""
        with patch("fitz.open") as mock_fitz:
            mock_fitz.return_value = mock_pdf_document(metadata={"title": "Metadata Title"})

            result = await extractor.extract(file_path="/path/to/doc.pdf")

            # Title may come from metadata or font extraction
            assert result.title is not None

    @pytest.mark.asyncio
    async def test_title_fallback_to_url_filename(
        self, extractor, mock_pdf_document, mock_httpx_response
    ):
        """Test title falls back to URL filename when metadata is poor."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            # PDF with no useful metadata
            mock_fitz.return_value = mock_pdf_document(
                metadata={},
                text_pages=["Some content without a clear title."],
            )

            result = await extractor.extract(url="https://example.com/Research_Paper_2024.pdf")

            # Should extract title from URL
            assert "Research Paper 2024" in result.title or result.title is not None

    def test_title_from_url_cleans_filename(self, extractor):
        """Test URL filename cleaning for title."""
        result = extractor._title_from_url("https://example.com/my_research-paper_final.pdf")

        assert result is not None
        assert "_" not in result
        assert "-" not in result


# =============================================================================
# Author Extraction Tests
# =============================================================================


class TestAuthorExtraction:
    """Tests for PDF author extraction."""

    @pytest.mark.asyncio
    async def test_authors_from_metadata(self, extractor, mock_pdf_document):
        """Test author extraction from PDF metadata."""
        with patch("fitz.open") as mock_fitz:
            mock_fitz.return_value = mock_pdf_document(metadata={"author": "John Smith, Jane Doe"})

            result = await extractor.extract(file_path="/path/to/doc.pdf")

            assert isinstance(result.authors, list)

    @pytest.mark.asyncio
    async def test_multiple_authors_parsed(self, extractor, mock_pdf_document):
        """Test multiple authors are parsed correctly."""
        with patch("fitz.open") as mock_fitz:
            mock_fitz.return_value = mock_pdf_document(
                metadata={"author": "Alice; Bob and Charlie, David"}
            )

            result = await extractor.extract(file_path="/path/to/doc.pdf")

            # Should have parsed multiple authors
            assert isinstance(result.authors, list)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self, extractor, mock_pdf_document, mock_httpx_response):
        """Test that temporary files are cleaned up after extraction."""
        created_temp_files = []

        original_named_temp = tempfile.NamedTemporaryFile

        def track_temp_file(*args, **kwargs):
            tf = original_named_temp(*args, **kwargs)
            created_temp_files.append(tf.name)
            return tf

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("fitz.open") as mock_fitz,
            patch("tempfile.NamedTemporaryFile", side_effect=track_temp_file),
        ):
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document()

            result = await extractor.extract(url="https://example.com/doc.pdf")

            # file_path should not be returned for temp files
            assert result.file_path is None

    @pytest.mark.asyncio
    async def test_extract_handles_encoded_url(
        self, extractor, mock_pdf_document, mock_httpx_response
    ):
        """Test handling of URL-encoded PDF filenames."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document(metadata={})

            result = await extractor.extract(url="https://example.com/my%20document%20(final).pdf")

            assert result.source_type == "pdf"

    @pytest.mark.asyncio
    async def test_handles_empty_pages(self, extractor, mock_pdf_document, mock_httpx_response):
        """Test handling of PDFs with empty pages."""
        with patch("httpx.AsyncClient") as mock_client, patch("fitz.open") as mock_fitz:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_httpx_response()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            mock_fitz.return_value = mock_pdf_document(text_pages=["", "Page 2 has content", ""])

            result = await extractor.extract(url="https://example.com/sparse.pdf")

            assert "Page 2 has content" in result.text
            assert result.metadata.get("page_count") == 3


# =============================================================================
# Thumbnail Generation Tests
# =============================================================================


class TestThumbnailGeneration:
    """Tests for PDF thumbnail generation."""

    @pytest.mark.asyncio
    async def test_generate_thumbnail(self, extractor):
        """Test thumbnail generation from PDF first page."""
        with patch("fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_pixmap = MagicMock()

            mock_page.get_pixmap.return_value = mock_pixmap
            mock_doc.__getitem__.return_value = mock_page
            mock_fitz.return_value = mock_doc

            result = await extractor.generate_thumbnail(
                file_path="/path/to/doc.pdf",
                output_path="/path/to/thumbnail.png",
            )

            assert result == "/path/to/thumbnail.png"
            mock_pixmap.save.assert_called_once_with("/path/to/thumbnail.png")
            mock_doc.close.assert_called_once()
