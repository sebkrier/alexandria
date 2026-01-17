"""
LiteLLM-based unified AI completion module.
Provides a single interface for all AI providers (Anthropic, OpenAI, Google).
"""

import json
import logging
import re
from typing import TypeVar

import litellm
from pydantic import BaseModel

from app.ai.base import AIProvider, CategoryInfo, CategorySuggestion, Summary, TagSuggestion
from app.ai.prompts import (
    CATEGORY_SYSTEM_PROMPT,
    CATEGORY_USER_PROMPT,
    EXTRACT_SUMMARY_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    QUESTION_USER_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    TAGS_SYSTEM_PROMPT,
    TAGS_USER_PROMPT,
    format_categories_for_prompt,
    truncate_text,
)

logger = logging.getLogger(__name__)

# Type variable for generic response model
T = TypeVar("T", bound=BaseModel)

# LiteLLM model prefixes for different providers
PROVIDER_PREFIXES = {
    "anthropic": "anthropic/",
    "openai": "",  # OpenAI models don't need a prefix
    "google": "gemini/",
}

# Available models per provider (for UI display)
PROVIDER_MODELS = {
    "anthropic": {
        "claude-opus-4-5-20251101": "Claude Opus 4.5 (Most capable)",
        "claude-sonnet-4-20250514": "Claude Sonnet 4 (Recommended)",
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet (Fast)",
        "claude-3-5-haiku-20241022": "Claude 3.5 Haiku (Fastest)",
    },
    "openai": {
        "gpt-4o": "GPT-4o (Recommended)",
        "gpt-4o-mini": "GPT-4o Mini (Fast)",
        "gpt-4-turbo": "GPT-4 Turbo",
        "o1": "o1 (Reasoning)",
    },
    "google": {
        "gemini-2.0-flash": "Gemini 2.0 Flash (Recommended)",
        "gemini-1.5-pro": "Gemini 1.5 Pro",
        "gemini-1.5-flash": "Gemini 1.5 Flash",
    },
}


async def complete(
    messages: list[dict],
    api_key: str,
    model: str,
    provider: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """
    Universal completion using LiteLLM.

    Args:
        messages: List of message dicts with 'role' and 'content'
        api_key: User's decrypted API key
        model: Model ID (e.g., 'claude-sonnet-4-20250514')
        provider: Provider name (e.g., 'anthropic', 'openai', 'google')
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Response content as string
    """
    # Build the full model name with provider prefix
    prefix = PROVIDER_PREFIXES.get(provider, "")
    full_model = f"{prefix}{model}"

    # Set the API key for LiteLLM
    # LiteLLM expects specific env var names, but we can pass directly
    response = await litellm.acompletion(
        model=full_model,
        messages=messages,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content


async def complete_stream(
    messages: list[dict],
    api_key: str,
    model: str,
    provider: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
):
    """
    Streaming completion using LiteLLM.

    Yields chunks of the response as they arrive.
    """
    from typing import AsyncGenerator

    prefix = PROVIDER_PREFIXES.get(provider, "")
    full_model = f"{prefix}{model}"

    response = await litellm.acompletion(
        model=full_model,
        messages=messages,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _extract_json(text: str) -> dict | list:
    """Extract JSON from model response, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block_match:
        text = code_block_match.group(1)

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

    json_str = text[start_idx : end_idx + 1]
    return json.loads(json_str)


class LiteLLMProvider(AIProvider):
    """
    Universal AI provider using LiteLLM.
    Supports Anthropic, OpenAI, and Google models through a unified interface.
    """

    def __init__(self, api_key: str, model_id: str, provider_name: str = "anthropic"):
        """
        Initialize the LiteLLM provider.

        Args:
            api_key: User's decrypted API key
            model_id: Model ID (e.g., 'claude-sonnet-4-20250514')
            provider_name: Provider name ('anthropic', 'openai', 'google')
        """
        self.api_key = api_key
        self.model_id = model_id
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def _complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """Internal completion helper."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return await complete(
            messages=messages,
            api_key=self.api_key,
            model=self.model_id,
            provider=self._provider_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def summarize(
        self,
        text: str,
        title: str | None = None,
        source_type: str | None = None,
    ) -> Summary:
        """Generate a structured summary."""
        user_prompt = EXTRACT_SUMMARY_PROMPT.format(
            title=title or "Untitled",
            source_type=source_type or "article",
            content=truncate_text(text),
        )

        try:
            markdown_content = await self._complete(
                system=SUMMARY_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=3000,
            )
            return Summary.from_markdown(markdown_content, title)
        except Exception as e:
            logger.error(f"LiteLLM summarization failed: {e}")
            raise

    async def suggest_tags(
        self,
        text: str,
        summary: str | None = None,
        existing_tags: list[str] | None = None,
    ) -> list[TagSuggestion]:
        """Suggest tags for the article."""
        existing_tags_context = ""
        if existing_tags:
            existing_tags_context = f"Existing tags in library: {', '.join(existing_tags)}\nPrefer using existing tags when appropriate."

        user_prompt = TAGS_USER_PROMPT.format(
            existing_tags_context=existing_tags_context,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 5000),
        )

        try:
            content = await self._complete(
                system=TAGS_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=1000,
            )
            json_data = _extract_json(content)

            if isinstance(json_data, list):
                return [TagSuggestion(**tag) for tag in json_data]
            return []
        except Exception as e:
            logger.error(f"LiteLLM tag suggestion failed: {e}")
            raise

    async def suggest_category(
        self,
        text: str,
        summary: str | None = None,
        categories: list[dict] | None = None,
    ) -> CategorySuggestion:
        """Suggest category placement."""
        categories_str = "No categories defined yet."
        if categories:
            categories_str = format_categories_for_prompt(categories)

        user_prompt = CATEGORY_USER_PROMPT.format(
            categories=categories_str,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 3000),
        )

        try:
            content = await self._complete(
                system=CATEGORY_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=500,
            )
            json_data = _extract_json(content)

            # Handle both old format (category_name/parent_category) and new format
            if "category" in json_data and isinstance(json_data["category"], str):
                # Old format - convert to new
                json_data = {
                    "category": CategoryInfo(
                        name=json_data.get(
                            "parent_category", json_data.get("category", "Uncategorized")
                        ),
                        is_new=json_data.get("is_new_category", False),
                    ),
                    "subcategory": CategoryInfo(
                        name=json_data.get("category_name", json_data.get("category")),
                        is_new=json_data.get(
                            "is_new_subcategory", json_data.get("is_new_category", False)
                        ),
                    ),
                    "confidence": json_data.get("confidence", 0.8),
                    "reasoning": json_data.get("reasoning", ""),
                }
                return CategorySuggestion(**json_data)

            return CategorySuggestion(**json_data)
        except Exception as e:
            logger.error(f"LiteLLM category suggestion failed: {e}")
            raise

    async def answer_question(
        self,
        question: str,
        context: str,
    ) -> str:
        """Answer a question using provided context."""
        user_prompt = QUESTION_USER_PROMPT.format(
            question=question,
            context=context,
        )

        try:
            return await self._complete(
                system=QUESTION_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=2000,
            )
        except Exception as e:
            logger.error(f"LiteLLM question answering failed: {e}")
            raise

    async def answer_question_stream(
        self,
        question: str,
        context: str,
    ):
        """Stream answer to a question using provided context."""
        user_prompt = QUESTION_USER_PROMPT.format(
            question=question,
            context=context,
        )

        messages = [
            {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        async for chunk in complete_stream(
            messages=messages,
            api_key=self.api_key,
            model=self.model_id,
            provider=self._provider_name,
            max_tokens=2000,
        ):
            yield chunk

    async def health_check(self) -> bool:
        """Check if the API key is valid."""
        try:
            await self._complete(
                system="You are a helpful assistant.",
                user="Hi",
                max_tokens=10,
            )
            return True
        except Exception as e:
            logger.error(f"LiteLLM health check failed: {e}")
            return False
