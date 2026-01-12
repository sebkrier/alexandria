import json
import logging
import re

import google.generativeai as genai

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


class GoogleProvider(AIProvider):
    """Google Gemini AI provider"""

    provider_name = "google"

    # Model options (2025)
    MODELS = {
        "gemini-2.0-flash": "Gemini 2.0 Flash (Latest, fast)",
        "gemini-1.5-pro": "Gemini 1.5 Pro (Most capable)",
        "gemini-1.5-flash": "Gemini 1.5 Flash (Fast)",
    }

    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str, model_id: str | None = None):
        genai.configure(api_key=api_key)
        self.model_id = model_id or self.DEFAULT_MODEL
        self.model = genai.GenerativeModel(self.model_id)

    async def summarize(
        self,
        text: str,
        title: str | None = None,
        source_type: str | None = None,
    ) -> Summary:
        """Generate a structured summary using Gemini"""
        user_prompt = EXTRACT_SUMMARY_PROMPT.format(
            title=title or "Untitled",
            source_type=source_type or "article",
            content=truncate_text(text),
        )

        full_prompt = f"{SUMMARY_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            response = await self.model.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=3000,
                    temperature=0.3,
                ),
            )

            # The new prompt returns markdown directly
            markdown_content = response.text

            return Summary.from_markdown(markdown_content, title)

        except Exception as e:
            logger.error(f"Google summarization failed: {e}")
            raise

    async def suggest_tags(
        self,
        text: str,
        summary: str | None = None,
        existing_tags: list[str] | None = None,
    ) -> list[TagSuggestion]:
        """Suggest tags using Gemini"""
        existing_tags_context = ""
        if existing_tags:
            existing_tags_context = f"Existing tags in library: {', '.join(existing_tags)}\nPrefer using existing tags when appropriate."

        user_prompt = TAGS_USER_PROMPT.format(
            existing_tags_context=existing_tags_context,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 5000),
        )

        full_prompt = f"{TAGS_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            response = await self.model.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=1000,
                    temperature=0.3,
                ),
            )

            content = response.text
            json_data = self._extract_json(content)

            if isinstance(json_data, list):
                return [TagSuggestion(**tag) for tag in json_data]
            return []

        except Exception as e:
            logger.error(f"Google tag suggestion failed: {e}")
            raise

    async def suggest_category(
        self,
        text: str,
        summary: str | None = None,
        categories: list[dict] | None = None,
    ) -> CategorySuggestion:
        """Suggest category using Gemini"""
        categories_str = "No categories defined yet."
        if categories:
            categories_str = format_categories_for_prompt(categories)

        user_prompt = CATEGORY_USER_PROMPT.format(
            categories=categories_str,
            summary=summary or "No summary provided",
            text_excerpt=truncate_text(text, 3000),
        )

        full_prompt = f"{CATEGORY_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            response = await self.model.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=500,
                    temperature=0.3,
                ),
            )

            content = response.text
            json_data = self._extract_json(content)

            return CategorySuggestion(**json_data)

        except Exception as e:
            logger.error(f"Google category suggestion failed: {e}")
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

        full_prompt = f"{QUESTION_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            response = await self.model.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=2000,
                    temperature=0.3,
                ),
            )

            return response.text

        except Exception as e:
            logger.error(f"Google question answering failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if the API key is valid"""
        try:
            response = await self.model.generate_content_async(
                "Hi",
                generation_config=genai.GenerationConfig(max_output_tokens=10),
            )
            return True
        except Exception as e:
            logger.error(f"Google health check failed: {e}")
            return False

    def _extract_json(self, text: str) -> dict | list:
        """Extract JSON from model response"""
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

        json_str = text[start_idx:end_idx + 1]
        return json.loads(json_str)
