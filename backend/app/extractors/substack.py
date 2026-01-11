"""Substack article extractor - handles Substack's bot protection"""

import asyncio
import subprocess
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup

from app.extractors.base import BaseExtractor, ExtractedContent


class SubstackExtractor(BaseExtractor):
    """Extract content from Substack articles.

    Uses curl for fetching because Cloudflare blocks Python HTTP libraries
    but allows curl requests.
    """

    TIMEOUT = 30

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is a Substack link"""
        parsed = urlparse(url)
        # Check for substack.com domain
        if "substack.com" in parsed.netloc:
            return True
        # Check for /p/ pattern in path (common Substack URL format)
        if "/p/" in parsed.path:
            return True
        return False

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not url:
            raise ValueError("URL is required for SubstackExtractor")

        # Try fetching the article
        html = await self._fetch_html(url)
        content = self._extract_content(html, url)

        # Strip timezone info from publication date (DB uses TIMESTAMP WITHOUT TIME ZONE)
        pub_date = content.get("publication_date")
        if pub_date and pub_date.tzinfo is not None:
            pub_date = pub_date.replace(tzinfo=None)

        return ExtractedContent(
            title=content.get("title", "Untitled"),
            text=self._clean_text(content.get("text", "")),
            authors=content.get("authors", []),
            publication_date=pub_date,
            source_type="url",
            original_url=url,
            metadata={
                "domain": urlparse(url).netloc,
                "subtitle": content.get("subtitle"),
            }
        )

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from Substack using curl.

        Cloudflare blocks Python HTTP libraries (httpx, requests) but allows curl,
        so we use subprocess to call curl for reliable fetching.
        """
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-L",
            "--max-time", str(self.TIMEOUT),
            "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: en-US,en;q=0.5",
            url,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Failed to fetch URL: {error_msg}")

        html = stdout.decode("utf-8", errors="replace")
        if not html or len(html) < 100:
            raise RuntimeError("Empty or invalid response from Substack")

        return html

    def _extract_content(self, html: str, url: str) -> dict:
        """Extract article content from Substack HTML"""
        # Use html.parser instead of lxml - lxml has issues with React Helmet meta tags
        soup = BeautifulSoup(html, "html.parser")

        # Title - try multiple selectors
        title = None
        # Try og:title meta tag first (most reliable)
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"]
        # Try Substack-specific class (with partial match)
        if not title:
            title_elem = soup.find("h1", class_=lambda x: x and "post-title" in x)
            if title_elem:
                title = title_elem.get_text(strip=True)
        # Try title tag (strip " - by Author" suffix)
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
                if " - by " in title:
                    title = title.split(" - by ")[0]
        # Try any h1
        if not title:
            title_elem = soup.find("h1")
            if title_elem:
                title = title_elem.get_text(strip=True)

        # Subtitle
        subtitle = None
        subtitle_elem = soup.find("h3", class_="subtitle")
        if subtitle_elem:
            subtitle = subtitle_elem.get_text(strip=True)

        # Author
        authors = []
        author_elem = soup.find("a", class_="frontend-pencraft-Text-module__decoration-hover-underline--BEYAn")
        if author_elem:
            authors = [author_elem.get_text(strip=True)]
        if not authors:
            # Try meta tag
            author_meta = soup.find("meta", {"name": "author"})
            if author_meta and author_meta.get("content"):
                authors = [author_meta["content"]]

        # Publication date
        pub_date = None
        time_elem = soup.find("time")
        if time_elem and time_elem.get("datetime"):
            try:
                pub_date = datetime.fromisoformat(time_elem["datetime"].replace("Z", "+00:00"))
            except ValueError:
                pass

        # Main content - Substack uses specific class
        main_content = soup.find("div", class_="body")
        if not main_content:
            main_content = soup.find("div", class_="post-content")
        if not main_content:
            main_content = soup.find("article")
        if not main_content:
            main_content = soup.body

        # Remove unwanted elements
        if main_content:
            for elem in main_content.find_all(["script", "style", "nav", "footer", "button"]):
                elem.decompose()
            # Remove subscription prompts
            for elem in main_content.find_all(class_=lambda x: x and ("subscribe" in x.lower() or "paywall" in x.lower())):
                elem.decompose()

        text = main_content.get_text(separator="\n", strip=True) if main_content else ""

        return {
            "title": title or "Untitled",
            "subtitle": subtitle,
            "text": text,
            "authors": authors,
            "publication_date": pub_date,
        }
