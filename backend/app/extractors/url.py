import logging
import re
from datetime import datetime
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.extractors.base import BaseExtractor, ExtractedContent
from app.extractors.constants import (
    ARCHIVE_TIMEOUT,
    BROWSER_HEADERS,
    BYPASS_TIMEOUT,
    DEFAULT_TIMEOUT,
    GOOGLE_REFERER_HEADERS,
    MOBILE_HEADERS,
)

logger = logging.getLogger(__name__)


class URLExtractor(BaseExtractor):
    """Extract content from general web URLs using multiple strategies"""

    TIMEOUT = DEFAULT_TIMEOUT

    # Headers are now sourced from constants module
    HEADERS = BROWSER_HEADERS
    HEADERS_FROM_GOOGLE = GOOGLE_REFERER_HEADERS
    MOBILE_HEADERS = MOBILE_HEADERS

    @staticmethod
    def can_handle(url: str) -> bool:
        """Generic URL extractor - handles all HTTP(S) URLs as fallback"""
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not url:
            raise ValueError("URL is required for URLExtractor")

        # Try multiple strategies to fetch the content
        html = None
        fetch_errors = []

        # Strategy 1: Direct fetch with standard headers
        try:
            html = await self._fetch_html(url, self.HEADERS)
            logger.info(f"Successfully fetched {url} with standard headers")
        except httpx.HTTPStatusError as e:
            fetch_errors.append(f"Direct fetch: {e.response.status_code}")
            logger.warning(f"Direct fetch failed for {url}: {e.response.status_code}")
        except Exception as e:
            fetch_errors.append(f"Direct fetch: {str(e)}")
            logger.warning(f"Direct fetch failed for {url}: {e}")

        # Strategy 2: Fetch pretending we came from Google
        if not html:
            try:
                html = await self._fetch_html(url, self.HEADERS_FROM_GOOGLE)
                logger.info(f"Successfully fetched {url} with Google referer")
            except httpx.HTTPStatusError as e:
                fetch_errors.append(f"Google referer: {e.response.status_code}")
            except Exception as e:
                fetch_errors.append(f"Google referer: {str(e)}")

        # Strategy 3: Try mobile headers
        if not html:
            try:
                html = await self._fetch_html(url, self.MOBILE_HEADERS)
                logger.info(f"Successfully fetched {url} with mobile headers")
            except httpx.HTTPStatusError as e:
                fetch_errors.append(f"Mobile headers: {e.response.status_code}")
            except Exception as e:
                fetch_errors.append(f"Mobile headers: {str(e)}")

        # Strategy 4: Try archive.org Wayback Machine
        if not html:
            try:
                html = await self._fetch_from_archive(url)
                if html:
                    logger.info(f"Successfully fetched {url} from archive.org")
            except Exception as e:
                fetch_errors.append(f"Archive.org: {str(e)}")
                logger.warning(f"Archive.org fetch failed for {url}: {e}")

        # Strategy 5: Try Google Cache
        if not html:
            try:
                html = await self._fetch_from_google_cache(url)
                if html:
                    logger.info(f"Successfully fetched {url} from Google Cache")
            except Exception as e:
                fetch_errors.append(f"Google Cache: {str(e)}")

        # Strategy 6: Try 12ft.io (paywall bypass)
        if not html:
            try:
                html = await self._fetch_from_12ft(url)
                if html:
                    logger.info(f"Successfully fetched {url} from 12ft.io")
            except Exception as e:
                fetch_errors.append(f"12ft.io: {str(e)}")

        if not html:
            error_details = "; ".join(fetch_errors)
            raise ValueError(
                f"Could not fetch content from {url}. This site may be blocking automated access or require a subscription. "
                f"Attempted strategies: {error_details}"
            )

        # Extract title reliably from HTML metadata (og:title, <title>, <h1>)
        # This is more reliable than readability's title extraction
        title, authors, pub_date, top_image = self._extract_metadata_from_html(html)

        # Try readability for body text extraction (it's good at finding article content)
        content = self._extract_with_readability(html, url)

        if not content or len(content.get("text", "")) < 100:
            # Fallback to basic BeautifulSoup extraction for body text
            content = self._extract_with_beautifulsoup(html, url)

        return ExtractedContent(
            title=title or content.get("title", "Untitled"),
            text=self._clean_text(content.get("text", "")),
            authors=authors or content.get("authors", []),
            publication_date=pub_date or content.get("publication_date"),
            source_type="url",
            original_url=url,
            metadata={
                "domain": urlparse(url).netloc,
                "top_image": top_image or content.get("top_image"),
            },
        )

    async def _fetch_html(self, url: str, headers: dict) -> str:
        """Fetch HTML content from URL with given headers"""
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.TIMEOUT,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def _fetch_from_archive(self, url: str) -> str | None:
        """Try to fetch content from archive.org Wayback Machine"""
        # First, check if there's a cached version
        api_url = f"https://archive.org/wayback/available?url={quote(url, safe='')}"

        async with httpx.AsyncClient(timeout=ARCHIVE_TIMEOUT) as client:
            try:
                response = await client.get(api_url)
                data = response.json()

                if data.get("archived_snapshots", {}).get("closest", {}).get("available"):
                    archive_url = data["archived_snapshots"]["closest"]["url"]
                    # Fetch the archived page
                    html_response = await client.get(archive_url, headers=self.HEADERS)
                    if html_response.status_code == 200:
                        return html_response.text
            except Exception as e:
                logger.debug(f"Archive.org lookup failed: {e}")

        return None

    async def _fetch_from_google_cache(self, url: str) -> str | None:
        """Try to fetch content from Google's cache"""
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote(url, safe='')}"

        async with httpx.AsyncClient(
            timeout=ARCHIVE_TIMEOUT, headers=self.HEADERS_FROM_GOOGLE, follow_redirects=True
        ) as client:
            try:
                response = await client.get(cache_url)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                logger.debug(f"Google Cache fetch failed: {e}")

        return None

    async def _fetch_from_12ft(self, url: str) -> str | None:
        """Try to fetch content via 12ft.io (paywall bypass service)"""
        bypass_url = f"https://12ft.io/{url}"

        async with httpx.AsyncClient(
            timeout=BYPASS_TIMEOUT, headers=self.HEADERS, follow_redirects=True
        ) as client:
            try:
                response = await client.get(bypass_url)
                if response.status_code == 200:
                    # 12ft returns a page with the content embedded
                    return response.text
            except Exception as e:
                logger.debug(f"12ft.io fetch failed: {e}")

        return None

    def _extract_metadata_from_html(self, html: str) -> tuple[str | None, list[str], datetime | None, str | None]:
        """
        Extract metadata (title, authors, date, image) from HTML meta tags.

        This is more reliable than readability's extraction because HTML meta tags
        (og:title, <title>, etc.) are explicitly set by the page author.

        Returns: (title, authors, publication_date, top_image)
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract title - priority: og:title > twitter:title > <title> > <h1>
        title = None
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

        if not title:
            twitter_title = soup.find("meta", {"name": "twitter:title"})
            if twitter_title and twitter_title.get("content"):
                title = twitter_title["content"].strip()

        if not title and soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Clean common suffixes like " | Site Name" or " - Blog Name"
            for sep in [" | ", " - ", " – ", " — "]:
                if sep in title:
                    # Keep the first part (usually the article title)
                    parts = title.split(sep)
                    if len(parts[0]) > 10:  # Make sure first part is substantial
                        title = parts[0].strip()
                    break

        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # Extract authors
        authors = []
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            author_text = author_meta["content"].strip()
            # Handle "By John Smith" format
            author_text = re.sub(r"^[Bb]y\s+", "", author_text)
            if author_text:
                authors = [author_text]

        if not authors:
            # Try article:author (used by some sites)
            article_author = soup.find("meta", {"property": "article:author"})
            if article_author and article_author.get("content"):
                authors = [article_author["content"].strip()]

        # Extract publication date
        pub_date = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                pub_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00"))
            except ValueError:
                pass

        if not pub_date:
            date_meta = soup.find("meta", {"name": "date"})
            if date_meta and date_meta.get("content"):
                try:
                    pub_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Extract top image
        top_image = None
        og_image = soup.find("meta", {"property": "og:image"})
        if og_image and og_image.get("content"):
            top_image = og_image["content"]

        return title, authors, pub_date, top_image

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
        except Exception as e:
            logger.warning(f"Readability extraction failed for {url}: {e}")
            return {}

    def _extract_with_beautifulsoup(self, html: str, url: str) -> dict:
        """Fallback extraction using BeautifulSoup heuristics"""
        soup = BeautifulSoup(html, "lxml")

        # Remove script, style, nav elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            element.decompose()

        # Try to find title
        title = None
        # Check og:title first (usually the cleanest)
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"]
        if not title and soup.title:
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
            ".article-body",
            ".story-body",
            ".entry-content",
            ".content-body",
            "#article-body",
            ".wsj-snippet-body",  # WSJ specific
            ".article__body",
            ".post-body",
        ]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if not main_content:
            main_content = soup.body if soup.body else soup

        # Get text
        text = main_content.get_text(separator="\n", strip=True)

        # Clean up text - remove excessive whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)

        # Try to find authors
        authors = []
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            authors = [author_meta["content"]]
        if not authors:
            # Try other common author patterns
            author_el = soup.select_one('[rel="author"], .author-name, .byline, .article-author')
            if author_el:
                author_text = author_el.get_text(strip=True)
                # Clean up "By John Smith" -> "John Smith"
                author_text = re.sub(r"^[Bb]y\s+", "", author_text)
                if author_text:
                    authors = [author_text]

        # Try to find publication date
        pub_date = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                pub_date = datetime.fromisoformat(date_meta["content"].replace("Z", "+00:00"))
            except ValueError:
                pass
        if not pub_date:
            # Try other date formats
            date_meta = soup.find("meta", {"name": "date"})
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
