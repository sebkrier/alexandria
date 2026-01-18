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

        # Try to extract authors from metadata or content
        authors = self._extract_authors(doc, full_text)

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
        # Try metadata first (but validate it's not just a filename or institution)
        if doc.metadata and doc.metadata.get("title"):
            title = doc.metadata["title"].strip()
            # Skip if it looks like a filename, institution, or generic text
            skip_patterns = [
                r"^Microsoft Word",
                r"^Universidad",
                r"^University",
                r"^\d+$",  # Just numbers
                r"^Document\d*$",
                r"\.docx?$",
                r"\.pdf$",
            ]
            is_valid = title and len(title) > 10
            for pattern in skip_patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    is_valid = False
                    break
            if is_valid:
                return title

        # For academic PDFs: find the best title candidate from first page
        lines = full_text.split("\n")[:40]
        candidates = []

        # Skip patterns for headers/footers/metadata
        skip_line_patterns = [
            r"^(Universidad|University|Institute|College|School)\s",
            r"^(Working Paper|Discussion Paper|Technical Report|ISSN|ISBN|DOI)",
            r"^(Serie|Series|Vol\.|Volume|No\.|Number|Issue)\s",
            r"^\d{4}$",  # Just a year
            r"^[\d\-\s]+$",  # Just numbers/dashes
            r"^(www\.|http|@|email)",
            r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d",
            r"^\s*$",  # Empty
            r"^(Abstract|Introduction|Keywords|JEL|Contents)(\s|:)",
        ]

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Skip short lines and lines matching skip patterns
            if len(line) < 15:
                continue

            should_skip = False
            for pattern in skip_line_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    should_skip = True
                    break
            if should_skip:
                continue

            # Skip lines that end with period (usually not titles)
            if line.endswith(".") and len(line) < 100:
                continue

            # Score the candidate
            score = len(line)  # Longer is often better for titles

            # Bonus for lines that look like titles
            if line[0].isupper():
                score += 20
            if ":" in line:  # Academic titles often have colons
                score += 15
            # Penalty for all caps (usually headers)
            if line.isupper() and len(line) < 50:
                score -= 30
            # Penalty for lines with too many special chars
            special_count = len(re.findall(r"[^\w\s\-:,']", line))
            score -= special_count * 5

            candidates.append((score, line, i))

        # Sort by score descending, take best
        candidates.sort(reverse=True)
        if candidates:
            return candidates[0][1]

        # Fallback to filename
        return Path(doc.name).stem if doc.name else "Untitled PDF"

    def _extract_authors(self, doc, full_text: str = None) -> list[str]:
        """Extract authors from PDF metadata or content"""
        authors = []

        # Try metadata first
        if doc.metadata:
            author_str = doc.metadata.get("author", "")
            if author_str:
                # Split by common separators
                meta_authors = re.split(r"[,;&]|\band\b", author_str)
                authors = [a.strip() for a in meta_authors if a.strip()]

        # If we didn't get authors from metadata, try to extract from text
        if not authors and full_text:
            lines = full_text.split("\n")[:30]

            # Look for lines that look like author names
            # Authors usually appear after the title, often with email/affiliation nearby
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or len(line) < 5:
                    continue

                # Skip obvious non-author lines
                if re.search(r"^(Abstract|Introduction|Universidad|University|http|www\.|@)", line, re.IGNORECASE):
                    continue
                if re.search(r"(Working Paper|ISSN|DOI|JEL|Keywords)", line, re.IGNORECASE):
                    continue

                # Author name patterns:
                # - Two or more capitalized words
                # - May have "and" between names
                # - Usually 15-60 chars
                if 10 < len(line) < 80:
                    # Check if it looks like names (capitalized words)
                    words = line.split()
                    cap_words = sum(1 for w in words if w and w[0].isupper())

                    # If most words are capitalized and it's 2-6 words, might be authors
                    if 2 <= len(words) <= 8 and cap_words >= len(words) * 0.7:
                        # Check it's not a title (titles are usually longer or have specific patterns)
                        if not re.search(r"[:\?\!]", line):  # Titles often have colons
                            # Split by "and" or commas to get individual names
                            potential_authors = re.split(r"\s+and\s+|,\s*", line)
                            for pa in potential_authors:
                                pa = pa.strip()
                                # Validate: should be 2+ words, proper capitalization
                                pa_words = pa.split()
                                if 2 <= len(pa_words) <= 4:
                                    authors.append(pa)
                            if authors:
                                break  # Found author line, stop

        return authors

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
