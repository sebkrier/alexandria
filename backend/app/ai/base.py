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
                for next_line in lines[i + 1 :]:
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


class CategoryInfo(BaseModel):
    """Category or subcategory info from AI"""

    name: str = Field(description="Name of the category/subcategory")
    is_new: bool = Field(default=False, description="Whether this is a new category to create")


class CategorySuggestion(BaseModel):
    """Suggested two-level category placement from AI"""

    category: CategoryInfo = Field(description="Top-level category")
    subcategory: CategoryInfo = Field(description="Subcategory within the category")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
    reasoning: str = Field(description="Why this categorization fits")


class SubcategoryAssignment(BaseModel):
    """Subcategory with assigned articles"""

    name: str = Field(description="Name of the subcategory")
    article_ids: list[str] = Field(description="IDs of articles in this subcategory")
    description: str = Field(default="", description="Brief description of the subcategory")


class CategoryStructure(BaseModel):
    """Category with its subcategories"""

    category: str = Field(description="Top-level category name")
    subcategories: list[SubcategoryAssignment] = Field(description="Subcategories with article assignments")


class TaxonomyChangesSummary(BaseModel):
    """Summary of changes in the proposed taxonomy"""

    new_categories: list[str] = Field(default_factory=list, description="New top-level categories")
    new_subcategories: list[str] = Field(default_factory=list, description="New subcategories")
    merged: list[str] = Field(default_factory=list, description="Categories that were merged")
    split: list[str] = Field(default_factory=list, description="Categories that were split")
    reorganized: list[str] = Field(default_factory=list, description="Articles that moved categories")


class TaxonomyOptimizationResult(BaseModel):
    """Result of taxonomy optimization analysis"""

    taxonomy: list[CategoryStructure] = Field(description="Proposed category structure")
    changes_summary: TaxonomyChangesSummary = Field(description="Summary of proposed changes")
    reasoning: str = Field(description="Explanation of the proposed structure")

    # Legacy properties for backward compatibility during transition
    @property
    def category_name(self) -> str:
        """Returns subcategory name (the most specific category)"""
        return self.subcategory.name

    @property
    def parent_category(self) -> str | None:
        """Returns parent category name"""
        return self.category.name

    @property
    def is_new_category(self) -> bool:
        """Returns True if either category or subcategory is new"""
        return self.category.is_new or self.subcategory.is_new


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

    async def generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate an embedding vector for the given text.

        Args:
            text: The text to embed (title + summary + content)

        Returns:
            Embedding vector as list of floats, or None if not supported
        """
        # Default implementation returns None (not supported)
        # Providers that support embeddings should override this
        return None

    @property
    def supports_embeddings(self) -> bool:
        """Whether this provider supports embedding generation"""
        return False
