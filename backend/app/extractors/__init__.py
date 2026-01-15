import logging

import httpx

from app.extractors.arxiv import ArxivExtractor
from app.extractors.base import BaseExtractor, ExtractedContent
from app.extractors.lesswrong import LessWrongExtractor
from app.extractors.pdf import PDFExtractor
from app.extractors.substack import SubstackExtractor
from app.extractors.url import URLExtractor
from app.extractors.youtube import YouTubeExtractor

logger = logging.getLogger(__name__)

# Order matters - first match wins
EXTRACTORS = [
    ArxivExtractor,
    SubstackExtractor,  # Before generic URL extractor
    YouTubeExtractor,  # Video platforms
    LessWrongExtractor,  # LessWrong/Alignment Forum (React SPA, needs API)
    PDFExtractor,
    URLExtractor,  # Generic fallback
]


async def _detect_content_type(url: str) -> str | None:
    """
    Make a HEAD request to detect Content-Type without downloading full content.
    Returns the content-type header or None if detection fails.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as client:
            response = await client.head(url)
            return response.headers.get("content-type", "").lower()
    except Exception as e:
        logger.debug(f"Content-Type detection failed for {url}: {e}")
        return None


async def extract_content(url: str = None, file_path: str = None) -> ExtractedContent:
    """
    Extract content from a URL or file path.
    Automatically selects the appropriate extractor.
    """
    if file_path:
        return await PDFExtractor().extract(file_path=file_path)

    if url:
        # First, try URL-based pattern matching
        for extractor_class in EXTRACTORS:
            if extractor_class.can_handle(url):
                extractor = extractor_class()
                try:
                    return await extractor.extract(url=url)
                except Exception as e:
                    logger.warning(f"{extractor_class.__name__} failed for {url}: {e}")
                    # Continue to next extractor or fallback
                    break

        # If pattern matching failed or extractor failed, try Content-Type detection
        content_type = await _detect_content_type(url)
        if content_type:
            logger.info(f"Detected Content-Type: {content_type} for {url}")

            # Handle PDF by Content-Type (even if URL doesn't end in .pdf)
            if "application/pdf" in content_type:
                logger.info("Using PDFExtractor based on Content-Type")
                return await PDFExtractor().extract(url=url)

            # Handle HTML/text with URLExtractor
            if "text/html" in content_type or "text/plain" in content_type:
                logger.info("Using URLExtractor based on Content-Type")
                return await URLExtractor().extract(url=url)

        # Final fallback: try URLExtractor for any URL
        logger.info(f"Using URLExtractor as final fallback for {url}")
        return await URLExtractor().extract(url=url)

    raise ValueError("Either url or file_path must be provided")


__all__ = [
    "BaseExtractor",
    "ExtractedContent",
    "URLExtractor",
    "PDFExtractor",
    "ArxivExtractor",
    "SubstackExtractor",
    "YouTubeExtractor",
    "LessWrongExtractor",
    "extract_content",
    "EXTRACTORS",
]
