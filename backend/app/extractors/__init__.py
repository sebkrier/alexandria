from app.extractors.base import BaseExtractor, ExtractedContent
from app.extractors.url import URLExtractor
from app.extractors.pdf import PDFExtractor
from app.extractors.arxiv import ArxivExtractor
from app.extractors.substack import SubstackExtractor
from app.extractors.youtube import YouTubeExtractor

# Order matters - first match wins
EXTRACTORS = [
    ArxivExtractor,
    SubstackExtractor,  # Before generic URL extractor
    YouTubeExtractor,  # Video platforms
    PDFExtractor,
    URLExtractor,  # Generic fallback
]


async def extract_content(url: str = None, file_path: str = None) -> ExtractedContent:
    """
    Extract content from a URL or file path.
    Automatically selects the appropriate extractor.
    """
    if file_path:
        return await PDFExtractor().extract(file_path=file_path)

    if url:
        for extractor_class in EXTRACTORS:
            if extractor_class.can_handle(url):
                extractor = extractor_class()
                return await extractor.extract(url=url)

    raise ValueError("Either url or file_path must be provided")


__all__ = [
    "BaseExtractor",
    "ExtractedContent",
    "URLExtractor",
    "PDFExtractor",
    "ArxivExtractor",
    "SubstackExtractor",
    "YouTubeExtractor",
    "extract_content",
    "EXTRACTORS",
]
