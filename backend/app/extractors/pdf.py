import logging
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from app.extractors.base import BaseExtractor, ExtractedContent
from app.extractors.constants import PDF_HEADERS, PDF_TIMEOUT

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    """Extract content from PDF files using PyMuPDF"""

    TIMEOUT = PDF_TIMEOUT
    HEADERS = PDF_HEADERS

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL points to a PDF"""
        # Check for Google Drive links (various formats)
        if "drive.google.com/file/d/" in url:
            return True
        if "drive.google.com/open?id=" in url:
            return True
        if "drive.google.com/uc?" in url and "id=" in url:
            return True

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
        title = self._clean_title(title)

        # Try to extract authors from metadata or content
        authors = self._extract_authors(doc, full_text)
        authors = [self._clean_title(a) for a in authors]  # Clean author names too

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
            except Exception as e:
                logger.debug(f"Failed to clean up temp file {temp_file}: {e}")

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

    def _convert_google_drive_url(self, url: str) -> str:
        """Convert Google Drive view/share URL to direct download URL."""
        # Pattern 1: https://drive.google.com/file/d/{FILE_ID}/view
        match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"

        # Pattern 2: https://drive.google.com/open?id={FILE_ID}
        match = re.search(r"drive\.google\.com/open\?id=([^&]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"

        # Pattern 3: Already a download URL - ensure export=download is present
        if "drive.google.com/uc?" in url:
            match = re.search(r"id=([^&]+)", url)
            if match and "export=download" not in url:
                file_id = match.group(1)
                return f"https://drive.google.com/uc?export=download&id={file_id}"

        return url

    async def _download_pdf(self, url: str) -> tuple[str, str]:
        """Download PDF from URL to a temp file. Returns (temp_file_path, file_path)."""
        # Convert Google Drive URLs to direct download links
        if "drive.google.com/file/d/" in url:
            url = self._convert_google_drive_url(url)
            logger.info(f"Converted Google Drive URL to: {url}")

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.TIMEOUT, headers=self.HEADERS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Handle Google Drive virus scan warning page for large files
            if "text/html" in content_type and "drive.google.com" in url:
                # Google shows a confirmation page for large files
                # Try to extract the confirm token and retry
                html_content = response.text
                confirm_match = re.search(r'confirm=([^&"]+)', html_content)
                if confirm_match:
                    confirm_token = confirm_match.group(1)
                    confirmed_url = f"{url}&confirm={confirm_token}"
                    logger.info("Retrying Google Drive download with confirm token")
                    response = await client.get(confirmed_url)
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")

            # Verify it's actually a PDF
            is_google_drive = "drive.google.com" in url
            if "application/pdf" not in content_type and not url.lower().endswith(".pdf"):
                # For Google Drive, also check if content starts with PDF magic bytes
                if is_google_drive and response.content[:4] == b"%PDF":
                    pass  # Valid PDF despite content-type
                else:
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
        except Exception as e:
            logger.debug(f"Could not extract title from URL {url}: {e}")
        return None

    def _extract_title_and_authors_from_font(self, doc) -> tuple[str | None, list[str]]:
        """Extract title and authors using font size information from first page."""
        try:
            page = doc[0]
            blocks = page.get_text("dict", flags=11)["blocks"]

            # Collect text spans with their font sizes and positions
            text_items = []
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    line_text = ""
                    max_size = 0
                    y_pos = line["bbox"][1]  # Top y position

                    for span in line["spans"]:
                        line_text += span["text"]
                        max_size = max(max_size, span["size"])

                    line_text = line_text.strip()
                    if line_text and max_size > 0:
                        text_items.append({"text": line_text, "size": max_size, "y": y_pos})

            if not text_items:
                return None, []

            # Sort by y position (top to bottom)
            text_items.sort(key=lambda x: x["y"])

            # Find the largest font size in the top portion of the page (likely title)
            top_items = [t for t in text_items if t["y"] < 400]  # Top ~half of page
            if not top_items:
                top_items = text_items[:20]

            max_font_size = max(t["size"] for t in top_items)

            # Title is usually the largest text, possibly spanning multiple lines
            title_parts = []
            title_font_threshold = max_font_size * 0.9  # Allow slight variation

            # Skip patterns for non-title text
            skip_patterns = [
                r"^(Universidad|University|Institute|College|School|Journal)\b",
                r"^(Working Paper|Discussion Paper|Technical Report|ISSN|ISBN|DOI|Vol\.|Volume)",
                r"^\d{4}$",
                r"^(www\.|http|@)",
                r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d",
            ]

            for item in top_items:
                if item["size"] >= title_font_threshold:
                    text = item["text"]
                    # Skip if matches skip pattern
                    should_skip = any(re.search(p, text, re.IGNORECASE) for p in skip_patterns)
                    if not should_skip and len(text) > 3:
                        title_parts.append(text)

            # Combine title parts (handle multi-line titles)
            title = " ".join(title_parts).strip() if title_parts else None

            # Clean up title - remove line break artifacts
            if title:
                title = re.sub(r"\s+", " ", title)
                # If title ends with hyphen followed by word, it was hyphenated
                title = re.sub(r"-\s+", "", title)

            # Find authors - typically second largest font, appears after title
            # Authors are usually between title and abstract
            if title_parts:
                title_end_y = max(t["y"] for t in top_items if t["size"] >= title_font_threshold)
            else:
                title_end_y = 0

            # Look for author-sized text after title
            font_sizes = sorted({t["size"] for t in top_items}, reverse=True)
            author_font_sizes = font_sizes[1:4] if len(font_sizes) > 1 else []  # 2nd-4th largest

            authors = []
            author_texts = []

            for item in text_items:
                # Authors should be below title but in top portion
                if item["y"] <= title_end_y:
                    continue
                if item["y"] > 500:  # Don't go too far down
                    break

                # Check if this could be author text (medium-large font)
                if item["size"] in author_font_sizes or (
                    author_font_sizes and item["size"] >= min(author_font_sizes) * 0.9
                ):
                    text = item["text"]

                    # Skip non-author patterns
                    if re.search(
                        r"^(Abstract|Introduction|Keywords|University|Department|@|http|www\.)",
                        text,
                        re.IGNORECASE,
                    ):
                        continue
                    if re.search(r"(ISSN|DOI|Working Paper)", text, re.IGNORECASE):
                        continue

                    # Check if it looks like names
                    if len(text) > 5 and len(text) < 200:
                        author_texts.append(text)

            # Parse author texts into individual names
            for text in author_texts:
                # Split by common separators
                potential = re.split(r"\s*[,;·•∗†‡§]\s*|\s+and\s+|\s{3,}", text)
                for p in potential:
                    p = p.strip()
                    # Remove footnote markers, affiliations in parens, email
                    p = re.sub(r"[\d∗†‡§]+$", "", p)
                    p = re.sub(r"\s*\([^)]*\)\s*", " ", p)
                    p = re.sub(r"\s*<[^>]*>\s*", "", p)
                    p = p.strip()

                    # Validate as name: 2-5 words, mostly capitalized
                    words = p.split()
                    if 2 <= len(words) <= 5:
                        cap_words = sum(1 for w in words if w and w[0].isupper())
                        if cap_words >= len(words) * 0.6:
                            # Not a title or institution
                            if not re.search(
                                r"(University|Institute|Department|Center|College)",
                                p,
                                re.IGNORECASE,
                            ):
                                authors.append(p)

            # Deduplicate while preserving order
            seen = set()
            unique_authors = []
            for a in authors:
                if a.lower() not in seen:
                    seen.add(a.lower())
                    unique_authors.append(a)

            return title, unique_authors[:15]  # Cap at 15 authors

        except Exception as e:
            logger.warning(f"Font-based extraction failed: {e}")
            return None, []

    def _extract_title(self, doc, full_text: str) -> str:
        """Extract title from PDF metadata or content"""
        # Try font-based extraction first (most reliable for academic papers)
        font_title, _ = self._extract_title_and_authors_from_font(doc)
        if font_title and len(font_title) > 10:
            return font_title

        # Try metadata (but validate it's not just a filename or institution)
        if doc.metadata and doc.metadata.get("title"):
            title = doc.metadata["title"].strip()
            skip_patterns = [
                r"^Microsoft Word",
                r"^Universidad",
                r"^University",
                r"^\d+$",
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

        # Fallback to text-based extraction
        lines = full_text.split("\n")[:40]
        skip_line_patterns = [
            r"^(Universidad|University|Institute|College|School)\s",
            r"^(Working Paper|Discussion Paper|Technical Report|ISSN|ISBN|DOI)",
            r"^\d{4}$",
            r"^[\d\-\s]+$",
            r"^(www\.|http|@|email)",
            r"^\s*$",
            r"^(Abstract|Introduction|Keywords|JEL|Contents)(\s|:)",
        ]

        for line in lines:
            line = line.strip()
            if len(line) < 15:
                continue
            if any(re.search(p, line, re.IGNORECASE) for p in skip_line_patterns):
                continue
            if line.endswith(".") and len(line) < 100:
                continue
            if line[0].isupper():
                return line

        return Path(doc.name).stem if doc.name else "Untitled PDF"

    def _extract_authors(self, doc, full_text: str = None) -> list[str]:
        """Extract authors from PDF metadata or content"""
        # Try font-based extraction first
        _, font_authors = self._extract_title_and_authors_from_font(doc)
        if font_authors:
            return font_authors

        # Try metadata
        authors = []
        if doc.metadata:
            author_str = doc.metadata.get("author", "")
            if author_str:
                meta_authors = re.split(r"[,;&]|\band\b", author_str)
                authors = [a.strip() for a in meta_authors if a.strip() and len(a.strip()) > 2]

        if authors:
            return authors

        # Fallback: look for author-like lines in text
        if full_text:
            lines = full_text.split("\n")[:30]
            for line in lines:
                line = line.strip()
                if not line or len(line) < 5 or len(line) > 150:
                    continue
                if re.search(
                    r"^(Abstract|Introduction|Universidad|University|http|www\.|@)",
                    line,
                    re.IGNORECASE,
                ):
                    continue

                # Check if looks like names
                words = line.split()
                if 2 <= len(words) <= 10:
                    cap_words = sum(1 for w in words if w and w[0].isupper())
                    if cap_words >= len(words) * 0.6:
                        potential = re.split(r"\s+and\s+|,\s*|;", line)
                        for p in potential:
                            p = p.strip()
                            p_words = p.split()
                            if 2 <= len(p_words) <= 4:
                                authors.append(p)
                        if authors:
                            return authors

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
