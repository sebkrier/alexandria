from datetime import datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.extractors.base import BaseExtractor, ExtractedContent


class URLExtractor(BaseExtractor):
    """Extract content from general web URLs using multiple strategies"""

    TIMEOUT = 30.0

    # More complete browser headers to avoid 403 blocks
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    @staticmethod
    def can_handle(url: str) -> bool:
        """Generic URL extractor - handles all HTTP(S) URLs as fallback"""
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not url:
            raise ValueError("URL is required for URLExtractor")

        html = await self._fetch_html(url)

        # Try newspaper3k-style extraction first
        content = self._extract_with_readability(html, url)

        if not content or len(content.get("text", "")) < 100:
            # Fallback to basic BeautifulSoup extraction
            content = self._extract_with_beautifulsoup(html, url)

        return ExtractedContent(
            title=content.get("title", "Untitled"),
            text=self._clean_text(content.get("text", "")),
            authors=content.get("authors", []),
            publication_date=content.get("publication_date"),
            source_type="url",
            original_url=url,
            metadata={
                "domain": urlparse(url).netloc,
                "top_image": content.get("top_image"),
            },
        )

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL"""
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.TIMEOUT, headers=self.HEADERS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _extract_with_readability(self, html: str, url: str) -> dict:
        """Extract using readability-lxml algorithm"""
        try:
            from readability import Document

            doc = Document(html)

            # Get title
            title = doc.title()

            # Get main content (returns HTML)
            content_html = doc.summary()

            # Convert HTML to plain text
            soup = BeautifulSoup(content_html, "lxml")
            text = soup.get_text(separator="\n", strip=True)

            return {
                "title": title,
                "text": text,
                "authors": [],
                "publication_date": None,
            }
        except Exception:
            return {}

    def _extract_with_beautifulsoup(self, html: str, url: str) -> dict:
        """Fallback extraction using BeautifulSoup heuristics"""
        soup = BeautifulSoup(html, "lxml")

        # Remove script, style, nav elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()

        # Try to find title
        title = None
        if soup.title:
            title = soup.title.string
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # Try to find main content
        main_content = None
        for selector in [
            "article",
            "main",
            '[role="main"]',
            ".post-content",
            ".article-content",
            ".entry-content",
        ]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if not main_content:
            main_content = soup.body if soup.body else soup

        # Get text
        text = main_content.get_text(separator="\n", strip=True)

        # Try to find authors
        authors = []
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            authors = [author_meta["content"]]

        # Try to find publication date
        pub_date = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                pub_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00"))
            except ValueError:
                pass

        # Try to find top image
        top_image = None
        og_image = soup.find("meta", {"property": "og:image"})
        if og_image and og_image.get("content"):
            top_image = og_image["content"]

        return {
            "title": title or "Untitled",
            "text": text,
            "authors": authors,
            "publication_date": pub_date,
            "top_image": top_image,
        }
