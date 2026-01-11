from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel


class ExtractedContent(BaseModel):
    """Standardized content extraction result"""
    title: str
    text: str
    authors: list[str] = []
    publication_date: datetime | None = None
    source_type: str  # 'url', 'pdf', 'arxiv'
    original_url: str | None = None
    file_path: str | None = None
    metadata: dict = {}

    class Config:
        extra = "allow"


class BaseExtractor(ABC):
    """Base class for content extractors"""

    @staticmethod
    @abstractmethod
    def can_handle(url: str) -> bool:
        """Check if this extractor can handle the given URL"""
        pass

    @abstractmethod
    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        """Extract content from the source"""
        pass

    def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing excessive whitespace"""
        if not text:
            return ""
        # Replace multiple newlines with double newlines
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def _truncate_text(self, text: str, max_length: int = 100000) -> str:
        """Truncate text to max length for very long documents"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "\n\n[Content truncated due to length...]"
