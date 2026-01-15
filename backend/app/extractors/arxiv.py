import asyncio
import re
import tempfile
from pathlib import Path

import arxiv

from app.extractors.base import BaseExtractor, ExtractedContent
from app.extractors.pdf import PDFExtractor


class ArxivExtractor(BaseExtractor):
    """Extract content from arXiv papers using the arXiv API"""

    # Updated patterns to handle more arXiv URL formats
    ARXIV_PATTERNS = [
        r"arxiv\.org/abs/(\d+\.\d+(?:v\d+)?)",  # arxiv.org/abs/2301.07041 or 2301.07041v1
        r"arxiv\.org/pdf/(\d+\.\d+(?:v\d+)?)",  # arxiv.org/pdf/2301.07041.pdf
        r"arxiv:(\d+\.\d+(?:v\d+)?)",  # arxiv:2301.07041
        r"arxiv\.org/abs/([a-z-]+/\d+)",  # Old format: arxiv.org/abs/hep-th/9901001
        r"arxiv\.org/pdf/([a-z-]+/\d+)",  # Old format PDF
    ]

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is an arXiv link"""
        url_lower = url.lower()
        return "arxiv.org" in url_lower or "arxiv:" in url_lower

    @staticmethod
    def extract_arxiv_id(url: str) -> str | None:
        """Extract arXiv ID from URL"""
        for pattern in ArxivExtractor.ARXIV_PATTERNS:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not url:
            raise ValueError("URL is required for ArxivExtractor")

        arxiv_id = self.extract_arxiv_id(url)
        if not arxiv_id:
            raise ValueError(f"Could not extract arXiv ID from URL: {url}")

        # Strip version suffix for API lookup if present
        base_id = re.sub(r"v\d+$", "", arxiv_id)

        # Fetch paper metadata from arXiv API (run in thread pool since it's blocking)
        paper = await asyncio.to_thread(self._fetch_paper, base_id)

        if not paper:
            raise ValueError(f"No paper found for arXiv ID: {arxiv_id}")

        # Download PDF to temporary file and extract full text
        full_text = await self._extract_pdf_text(paper)

        # Strip timezone info from publication date (DB uses TIMESTAMP WITHOUT TIME ZONE)
        pub_date = paper.published
        if pub_date and pub_date.tzinfo is not None:
            pub_date = pub_date.replace(tzinfo=None)

        return ExtractedContent(
            title=paper.title,
            text=full_text,
            authors=[author.name for author in paper.authors],
            publication_date=pub_date,
            source_type="arxiv",
            original_url=url,
            metadata={
                "arxiv_id": arxiv_id,
                "abstract": paper.summary,
                "categories": list(paper.categories) if paper.categories else [],
                "primary_category": str(paper.primary_category) if paper.primary_category else None,
                "pdf_url": paper.pdf_url,
                "doi": paper.doi,
                "journal_ref": paper.journal_ref,
                "comment": paper.comment,
            },
        )

    def _fetch_paper(self, arxiv_id: str):
        """Fetch paper from arXiv API (blocking)"""
        search = arxiv.Search(id_list=[arxiv_id])
        results = list(search.results())
        return results[0] if results else None

    async def _extract_pdf_text(self, paper) -> str:
        """Download arXiv PDF and extract text"""
        # Create temporary directory for PDF
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / f"{paper.get_short_id()}.pdf"

            # Download PDF (blocking operation, run in thread pool)
            def download():
                paper.download_pdf(dirpath=temp_dir, filename=pdf_path.name)

            await asyncio.to_thread(download)

            # Extract text using PDF extractor
            pdf_extractor = PDFExtractor()
            content = await pdf_extractor.extract(file_path=str(pdf_path))

            return content.text
