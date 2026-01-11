import json
import logging

from anthropic import AsyncAnthropic

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


class AnthropicProvider(AIProvider):
    """Anthropic Claude AI provider"""

    provider_name = "anthropic"

    # Model options (2025)
    MODELS = {
        "claude-opus-4-5-20251101": "Claude Opus 4.5 (Most capable)",
        "claude-sonnet-4-20250514": "Claude Sonnet 4 (Recommended)",
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet (Fast)",
        "claude-3-5-haiku-20241022": "Claude 3.5 Haiku (Fastest)",
    }

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str, model_id: str | None = None):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model_id = model_id or self.DEFAULT_MODEL

    async def summarize(
        self,
        text: str,
        title: str | None = None,
        source_type: str | None = None,
    ) -> Summary:
        """Generate a structured summary using Claude"""
        # Prepare the content with title context
        content_with_context = text
        if title:
            content_with_context = f"Title: {title}\n\n{text}"

        user_prompt = EXTRACT_SUMMARY_PROMPT.format(
            content=truncate_text(content_with_context),
        )

        try:
            response = await self.client.messages.create(
                model=self.model_id,
                max_tokens=3000,
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # The new prompt returns markdown directly
            markdown_content = response.content[0].text

            # Return Summary with markdown content
            return Summary.from_markdown(markdown_content, title)

        except Exception as e:
            logger.error(f"Anthropic summarization failed: {e}")
            raise

    async def suggest_tags(
        self,
        text: str,
        summary: str | None = None,
        existing_tags: list[str] | None = None,
    ) -> list[TagSuggestion]:
        """Suggest tags using Claude"""
        existing_tags_context = ""
        if existing_tags:
            existing_tags_context = f"Existing tags in library: {', '.join(existing_tags)}\nPrefer using existing tags when appropriate."

        user_prompt = TAGS_USER_PROMPT.format(
            existing_tags_context=existing_tags_context,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 5000),
        )

        try:
            response = await self.client.messages.create(
                model=self.model_id,
                max_tokens=1000,
                system=TAGS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content[0].text
            json_data = self._extract_json(content)

            if isinstance(json_data, list):
                return [TagSuggestion(**tag) for tag in json_data]
            return []

        except Exception as e:
            logger.error(f"Anthropic tag suggestion failed: {e}")
            raise

    async def suggest_category(
        self,
        text: str,
        summary: str | None = None,
        categories: list[dict] | None = None,
    ) -> CategorySuggestion:
        """Suggest category using Claude"""
        categories_str = "No categories defined yet."
        if categories:
            categories_str = format_categories_for_prompt(categories)

        user_prompt = CATEGORY_USER_PROMPT.format(
            categories=categories_str,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 3000),
        )

        try:
            response = await self.client.messages.create(
                model=self.model_id,
                max_tokens=500,
                system=CATEGORY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content[0].text
            json_data = self._extract_json(content)

            return CategorySuggestion(**json_data)

        except Exception as e:
            logger.error(f"Anthropic category suggestion failed: {e}")
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
            response = await self.client.messages.create(
                model=self.model_id,
                max_tokens=2000,
                system=QUESTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic question answering failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if the API key is valid"""
        try:
            # Make a minimal API call to verify the key works
            response = await self.client.messages.create(
                model=self.model_id,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic health check failed: {e}")
            return False

    def _extract_json(self, text: str) -> dict | list:
        """Extract JSON from model response, handling markdown code blocks"""
        # Try to find JSON in code blocks first
        import re
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if code_block_match:
            text = code_block_match.group(1)

        # Try to find JSON object or array
        text = text.strip()

        # Find the start of JSON
        start_idx = -1
        for i, char in enumerate(text):
            if char in "{[":
                start_idx = i
                break

        if start_idx == -1:
            raise ValueError(f"No JSON found in response: {text[:200]}")

        # Find matching end
        bracket_stack = []
        end_idx = start_idx
        for i in range(start_idx, len(text)):
            char = text[i]
            if char in "{[":
                bracket_stack.append(char)
            elif char == "}" and bracket_stack and bracket_stack[-1] == "{":
                bracket_stack.pop()
                if not bracket_stack:
                    end_idx = i
                    break
            elif char == "]" and bracket_stack and bracket_stack[-1] == "[":
                bracket_stack.pop()
                if not bracket_stack:
                    end_idx = i
                    break

        json_str = text[start_idx:end_idx + 1]
        return json.loads(json_str)
