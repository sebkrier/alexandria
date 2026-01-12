import json
import logging
import re

from openai import AsyncOpenAI

from app.ai.base import AIProvider, Summary, TagSuggestion, CategorySuggestion
from app.ai.prompts import (
    SUMMARY_SYSTEM_PROMPT,
    EXTRACT_SUMMARY_PROMPT,
    TAGS_SYSTEM_PROMPT,
    TAGS_USER_PROMPT,
    CATEGORY_SYSTEM_PROMPT,
    CATEGORY_USER_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    QUESTION_USER_PROMPT,
    format_categories_for_prompt,
    truncate_text,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""

    provider_name = "openai"

    # Model options (2025)
    MODELS = {
        "gpt-4o": "GPT-4o (Recommended)",
        "gpt-4o-mini": "GPT-4o Mini (Fast, efficient)",
        "o1": "o1 (Advanced reasoning)",
        "o1-mini": "o1-mini (Fast reasoning)",
    }

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str, model_id: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_id = model_id or self.DEFAULT_MODEL

    async def summarize(
        self,
        text: str,
        title: str | None = None,
        source_type: str | None = None,
    ) -> Summary:
        """Generate a structured summary using GPT"""
        user_prompt = EXTRACT_SUMMARY_PROMPT.format(
            title=title or "Untitled",
            source_type=source_type or "article",
            content=truncate_text(text),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                max_tokens=3000,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

            # The new prompt returns markdown directly
            markdown_content = response.choices[0].message.content

            return Summary.from_markdown(markdown_content, title)

        except Exception as e:
            logger.error(f"OpenAI summarization failed: {e}")
            raise

    async def suggest_tags(
        self,
        text: str,
        summary: str | None = None,
        existing_tags: list[str] | None = None,
    ) -> list[TagSuggestion]:
        """Suggest tags using GPT"""
        existing_tags_context = ""
        if existing_tags:
            existing_tags_context = f"Existing tags in library: {', '.join(existing_tags)}\nPrefer using existing tags when appropriate."

        user_prompt = TAGS_USER_PROMPT.format(
            existing_tags_context=existing_tags_context,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 5000),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                max_tokens=1000,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": TAGS_SYSTEM_PROMPT + "\n\nYou must respond with valid JSON. Wrap the array in an object like {\"tags\": [...]}"},
                    {"role": "user", "content": user_prompt},
                ],
            )

            content = response.choices[0].message.content
            json_data = json.loads(content)

            # Handle wrapped response
            if isinstance(json_data, dict) and "tags" in json_data:
                json_data = json_data["tags"]

            if isinstance(json_data, list):
                return [TagSuggestion(**tag) for tag in json_data]
            return []

        except Exception as e:
            logger.error(f"OpenAI tag suggestion failed: {e}")
            raise

    async def suggest_category(
        self,
        text: str,
        summary: str | None = None,
        categories: list[dict] | None = None,
    ) -> CategorySuggestion:
        """Suggest category using GPT"""
        categories_str = "No categories defined yet."
        if categories:
            categories_str = format_categories_for_prompt(categories)

        user_prompt = CATEGORY_USER_PROMPT.format(
            categories=categories_str,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 3000),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                max_tokens=500,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": CATEGORY_SYSTEM_PROMPT + "\n\nYou must respond with valid JSON."},
                    {"role": "user", "content": user_prompt},
                ],
            )

            content = response.choices[0].message.content
            json_data = json.loads(content)

            return CategorySuggestion(**json_data)

        except Exception as e:
            logger.error(f"OpenAI category suggestion failed: {e}")
            raise

    async def answer_question(
        self,
        question: str,
        context: str,
    ) -> str:
        """Answer a question using provided article context"""
        user_prompt = QUESTION_USER_PROMPT.format(
            question=question,
            context=context,
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI question answering failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if the API key is valid"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False

    # Embedding support
    EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions, cost-effective
    EMBEDDING_MAX_TOKENS = 8191  # Max input tokens for embedding model

    @property
    def supports_embeddings(self) -> bool:
        """OpenAI supports embeddings"""
        return True

    async def generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate an embedding vector using OpenAI's embedding model.

        Args:
            text: The text to embed (will be truncated if too long)

        Returns:
            1536-dimensional embedding vector
        """
        try:
            # Truncate text if too long (rough estimate: 4 chars per token)
            max_chars = self.EMBEDDING_MAX_TOKENS * 4
            if len(text) > max_chars:
                text = text[:max_chars]

            response = await self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text,
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            return None
