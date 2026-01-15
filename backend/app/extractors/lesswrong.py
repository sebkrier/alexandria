"""
LessWrong extractor using their GraphQL API.
LessWrong is a React SPA, so we can't just scrape HTML - we need to use their API.
"""

import re
import httpx
from datetime import datetime
from urllib.parse import urlparse

from app.extractors.base import BaseExtractor, ExtractedContent


class LessWrongExtractor(BaseExtractor):
    """Extract content from LessWrong posts using their GraphQL API"""

    GRAPHQL_ENDPOINT = "https://www.lesswrong.com/graphql"

    # Also handles Alignment Forum (same platform)
    DOMAINS = ["lesswrong.com", "www.lesswrong.com", "alignmentforum.org", "www.alignmentforum.org"]

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is a LessWrong or Alignment Forum post"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Must be a post URL (contains /posts/)
        if not any(d in domain for d in ["lesswrong.com", "alignmentforum.org"]):
            return False

        return "/posts/" in parsed.path

    def _extract_post_id(self, url: str) -> str | None:
        """Extract post ID from LessWrong URL"""
        # URL format: https://www.lesswrong.com/posts/{postId}/{slug}
        match = re.search(r"/posts/([a-zA-Z0-9]+)", url)
        return match.group(1) if match else None

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not url:
            raise ValueError("URL is required for LessWrongExtractor")

        post_id = self._extract_post_id(url)
        if not post_id:
            raise ValueError(f"Could not extract post ID from URL: {url}")

        # GraphQL query to get post content
        query = """
        query PostContent($postId: String!) {
            post(input: {selector: {_id: $postId}}) {
                result {
                    _id
                    title
                    slug
                    postedAt
                    htmlBody
                    contents {
                        markdown
                        plaintextMainText
                    }
                    user {
                        displayName
                        username
                    }
                    coauthors {
                        displayName
                        username
                    }
                }
            }
        }
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.GRAPHQL_ENDPOINT,
                json={
                    "query": query,
                    "variables": {"postId": post_id}
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Alexandria/1.0 (Article Reader)",
                }
            )
            response.raise_for_status()
            data = response.json()

        # Extract post data
        post = data.get("data", {}).get("post", {}).get("result")
        if not post:
            raise ValueError(f"Post not found: {post_id}")

        # Get title
        title = post.get("title", "Untitled")

        # Get text content (prefer plaintext, fall back to markdown)
        contents = post.get("contents") or {}
        text = contents.get("plaintextMainText") or contents.get("markdown") or ""

        # If no text from contents, try to extract from HTML body
        if not text and post.get("htmlBody"):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(post["htmlBody"], "lxml")
            text = soup.get_text(separator="\n", strip=True)

        # Get authors
        authors = []
        if post.get("user"):
            authors.append(post["user"].get("displayName") or post["user"].get("username", ""))
        for coauthor in post.get("coauthors") or []:
            authors.append(coauthor.get("displayName") or coauthor.get("username", ""))

        # Get publication date (strip timezone for database compatibility)
        pub_date = None
        if post.get("postedAt"):
            try:
                dt = datetime.fromisoformat(post["postedAt"].replace("Z", "+00:00"))
                # Convert to naive datetime (remove timezone info)
                pub_date = dt.replace(tzinfo=None)
            except ValueError:
                pass

        return ExtractedContent(
            title=title,
            text=self._clean_text(text),
            authors=authors,
            publication_date=pub_date,
            source_type="url",
            original_url=url,
            metadata={
                "domain": urlparse(url).netloc,
                "post_id": post_id,
                "platform": "lesswrong",
            }
        )
