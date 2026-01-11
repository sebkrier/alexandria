import re
from pathlib import Path

from app.extractors.base import BaseExtractor, ExtractedContent


class PDFExtractor(BaseExtractor):
    """Extract content from PDF files using PyMuPDF"""

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL points to a PDF"""
        return url.lower().endswith(".pdf")

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not file_path:
            raise ValueError("file_path is required for PDFExtractor")

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

        return ExtractedContent(
            title=title,
            text=full_text,
            authors=authors,
            publication_date=None,  # PDF metadata dates are often unreliable
            source_type="pdf",
            original_url=url,
            file_path=file_path,
            metadata={
                "page_count": len(text_parts),
                "pdf_metadata": metadata,
            }
        )

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
