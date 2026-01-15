import logging
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from app.extractors.base import BaseExtractor, ExtractedContent

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    """Extract content from PDF files using PyMuPDF"""

    TIMEOUT = 60.0  # PDFs can be large, allow more time

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL points to a PDF"""
        # Check URL extension
        parsed = urlparse(url.lower())
        path = unquote(parsed.path)
        return path.endswith(".pdf")

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        # If we have a URL but no file_path, download the PDF first
        temp_file = None
        if url and not file_path:
            logger.info(f"Downloading PDF from URL: {url}")
            temp_file, file_path = await self._download_pdf(url)

        if not file_path:
            raise ValueError("Either url or file_path is required for PDFExtractor")

        import fitz  # PyMuPDF

        doc = fitz.open(file_path)

        # Extract text from all pages
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())

        full_text = "\n\n".join(text_parts)
        full_text = self._clean_text(full_text)
        full_text = self._truncate_text(full_text)

        # Try to extract title from metadata or first page
        title = self._extract_title(doc, full_text)

        # Try to extract authors from metadata
        authors = self._extract_authors(doc)

        # Get metadata
        metadata = doc.metadata or {}

        doc.close()

        # If title wasn't found or looks like a domain, try URL filename
        is_poor_title = (
            title in ("Untitled PDF", None)
            or len(title) < 5
            or (title.count(".") >= 1 and len(title) < 30)  # Looks like domain
        )
        if is_poor_title and url:
            url_title = self._title_from_url(url)
            if url_title and len(url_title) > len(title or ""):
                title = url_title

        # Clean up temp file if we created one
        if temp_file:
            try:
                Path(temp_file).unlink()
            except Exception:
                pass

        return ExtractedContent(
            title=title,
            text=full_text,
            authors=authors,
            publication_date=None,  # PDF metadata dates are often unreliable
            source_type="pdf",
            original_url=url,
            file_path=file_path if not temp_file else None,  # Don't return temp path
            metadata={
                "page_count": len(text_parts),
                "pdf_metadata": metadata,
            },
        )

    async def _download_pdf(self, url: str) -> tuple[str, str]:
        """Download PDF from URL to a temp file. Returns (temp_file_path, file_path)."""
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.TIMEOUT, headers=self.HEADERS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Verify it's actually a PDF
            content_type = response.headers.get("content-type", "")
            if "application/pdf" not in content_type and not url.lower().endswith(".pdf"):
                raise ValueError(f"URL does not point to a PDF (content-type: {content_type})")

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(response.content)
            temp_file.close()

            logger.info(f"Downloaded PDF to {temp_file.name} ({len(response.content)} bytes)")
            return temp_file.name, temp_file.name

    def _title_from_url(self, url: str) -> str | None:
        """Extract a readable title from the URL filename."""
        try:
            parsed = urlparse(url)
            filename = unquote(Path(parsed.path).stem)
            # Clean up common URL artifacts
            filename = filename.replace("_", " ").replace("-", " ")
            # Remove extra whitespace
            filename = " ".join(filename.split())
            if len(filename) > 5:
                return filename
        except Exception:
            pass
        return None

    def _extract_title(self, doc, full_text: str) -> str:
        """Extract title from PDF metadata or content"""
        # Try metadata first
        if doc.metadata and doc.metadata.get("title"):
            title = doc.metadata["title"].strip()
            if title and len(title) > 3:  # Sanity check
                return title

        # Try to find title from first page content
        # Usually the title is in the first few lines and is larger/bolder
        lines = full_text.split("\n")[:20]
        for line in lines:
            line = line.strip()
            # Heuristic: title is usually 10-200 chars, no periods at end
            if 10 < len(line) < 200 and not line.endswith(".") and not line.startswith("http"):
                return line

        # Fallback to filename
        return Path(doc.name).stem if doc.name else "Untitled PDF"

    def _extract_authors(self, doc) -> list[str]:
        """Extract authors from PDF metadata"""
        if not doc.metadata:
            return []

        author_str = doc.metadata.get("author", "")
        if not author_str:
            return []

        # Split by common separators
        authors = re.split(r"[,;&]|\band\b", author_str)
        return [a.strip() for a in authors if a.strip()]

    async def generate_thumbnail(self, file_path: str, output_path: str) -> str:
        """Generate a thumbnail from the first page of the PDF"""
        import fitz

        doc = fitz.open(file_path)
        page = doc[0]

        # Render at 150 DPI for thumbnail
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)

        pix.save(output_path)
        doc.close()

        return output_path
