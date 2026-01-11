from abc import ABC, abstractmethod
from pydantic import BaseModel, Field


class Summary(BaseModel):
    """Summary output from AI - now stores raw markdown"""
    markdown: str = Field(description="The full markdown summary")
    abstract: str = Field(default="", description="One-line summary extracted for tags/categories")

    @classmethod
    def from_markdown(cls, markdown: str, title: str | None = None) -> "Summary":
        """Create Summary from raw markdown output"""
        # Extract the one-line summary for use in tag/category suggestions
        abstract = ""
        lines = markdown.split("\n")
        for i, line in enumerate(lines):
            # Look for "One-Line Summary" section
            if "one-line summary" in line.lower() or "one line summary" in line.lower():
                # Get the next non-empty line
                for next_line in lines[i+1:]:
                    next_line = next_line.strip()
                    if next_line and not next_line.startswith("#"):
                        abstract = next_line
                        break
                break

        # Fallback: use first paragraph after any heading
        if not abstract:
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 20:
                    abstract = line[:500]
                    break

        return cls(markdown=markdown, abstract=abstract)

    def to_markdown(self) -> str:
        """Return the markdown summary"""
        return self.markdown


class TagSuggestion(BaseModel):
    """Suggested tag from AI"""
    name: str = Field(description="The tag name (lowercase, hyphenated)")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
    reasoning: str = Field(description="Brief explanation of why this tag fits")


class CategorySuggestion(BaseModel):
    """Suggested category placement from AI"""
    category_name: str = Field(description="Name of the suggested category")
    parent_category: str | None = Field(
        default=None,
        description="Parent category if this is a subcategory"
    )
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
    reasoning: str = Field(description="Why this category fits")
    is_new_category: bool = Field(
        default=False,
        description="Whether this suggests creating a new category"
    )


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    provider_name: str = "base"

    @abstractmethod
    async def summarize(
        self,
        text: str,
        title: str | None = None,
        source_type: str | None = None,
    ) -> Summary:
        """
        Generate a structured summary of the article.

        Args:
            text: The full text of the article
            title: Optional existing title
            source_type: Type of source (url, pdf, arxiv)

        Returns:
            Structured Summary object
        """
        pass

    @abstractmethod
    async def suggest_tags(
        self,
        text: str,
        summary: str | None = None,
        existing_tags: list[str] | None = None,
    ) -> list[TagSuggestion]:
        """
        Suggest relevant tags for the article.

        Args:
            text: The article text (or summary for efficiency)
            summary: Optional pre-generated summary
            existing_tags: List of existing tag names in the user's library

        Returns:
            List of suggested tags with confidence scores
        """
        pass

    @abstractmethod
    async def suggest_category(
        self,
        text: str,
        summary: str | None = None,
        categories: list[dict] | None = None,
    ) -> CategorySuggestion:
        """
        Suggest which category this article belongs to.

        Args:
            text: The article text (or summary for efficiency)
            summary: Optional pre-generated summary
            categories: Existing category tree structure

        Returns:
            Category suggestion with confidence
        """
        pass

    @abstractmethod
    async def answer_question(
        self,
        question: str,
        context: str,
    ) -> str:
        """
        Answer a question using the provided article context.

        Args:
            question: The user's question
            context: Concatenated article content to use as context

        Returns:
            The answer as a string
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and API key is valid"""
        pass
