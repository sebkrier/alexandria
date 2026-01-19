"""
Tests for the AI Providers (Anthropic, OpenAI, Google).

Tests each provider's implementation of the AIProvider interface:
- Summarization
- Tag suggestion
- Category suggestion
- Question answering
- Health check
- JSON extraction
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.base import Summary


# =============================================================================
# Mock Response Classes
# =============================================================================


class MockAnthropicMessage:
    """Mock Anthropic message response."""

    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


class MockOpenAIChoice:
    """Mock OpenAI choice."""

    def __init__(self, content: str):
        self.message = MagicMock(content=content)


class MockOpenAIResponse:
    """Mock OpenAI chat completion response."""

    def __init__(self, content: str):
        self.choices = [MockOpenAIChoice(content)]


class MockOpenAIEmbeddingData:
    """Mock OpenAI embedding data."""

    def __init__(self, embedding: list[float]):
        self.embedding = embedding


class MockOpenAIEmbeddingResponse:
    """Mock OpenAI embedding response."""

    def __init__(self, embedding: list[float]):
        self.data = [MockOpenAIEmbeddingData(embedding)]


class MockGeminiResponse:
    """Mock Google Gemini response."""

    def __init__(self, text: str):
        self.text = text


# =============================================================================
# Sample Test Data
# =============================================================================


SAMPLE_MARKDOWN_SUMMARY = """## One-Line Summary
A groundbreaking paper on transformer architecture for NLP.

## Key Points
- Introduces self-attention mechanism
- Eliminates recurrence and convolutions
- Achieves state-of-the-art results

## Technical Details
The model uses multi-head attention."""

SAMPLE_TAGS_JSON = """[
    {"name": "machine-learning", "confidence": 0.95, "reasoning": "Core topic"},
    {"name": "transformers", "confidence": 0.90, "reasoning": "Main subject"}
]"""

SAMPLE_CATEGORY_JSON = """{
    "category": {"name": "AI & ML", "is_new": false},
    "subcategory": {"name": "Deep Learning", "is_new": true},
    "confidence": 0.88,
    "reasoning": "Focuses on neural network architecture"
}"""


# =============================================================================
# Anthropic Provider Tests
# =============================================================================


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        with patch("app.ai.providers.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_init_creates_client(self, mock_anthropic_client):
        """Test that __init__ creates AsyncAnthropic client."""
        from app.ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")

        assert provider.model_id == AnthropicProvider.DEFAULT_MODEL
        assert provider.provider_name == "anthropic"

    @pytest.mark.asyncio
    async def test_init_with_custom_model(self, mock_anthropic_client):
        """Test init with custom model."""
        from app.ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key", model_id="claude-haiku-4-5-20251101")

        assert provider.model_id == "claude-haiku-4-5-20251101"

    @pytest.mark.asyncio
    async def test_summarize_success(self, mock_anthropic_client):
        """Test successful summarization."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            return_value=MockAnthropicMessage(SAMPLE_MARKDOWN_SUMMARY)
        )

        provider = AnthropicProvider(api_key="test-key")
        summary = await provider.summarize(
            text="Sample article about transformers.",
            title="Attention Is All You Need",
            source_type="arxiv",
        )

        assert isinstance(summary, Summary)
        assert "transformer" in summary.abstract.lower()
        mock_anthropic_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_error_propagates(self, mock_anthropic_client):
        """Test that summarize errors are propagated."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        provider = AnthropicProvider(api_key="test-key")

        with pytest.raises(Exception, match="API Error"):
            await provider.summarize(text="Test")

    @pytest.mark.asyncio
    async def test_suggest_tags_success(self, mock_anthropic_client):
        """Test successful tag suggestion."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            return_value=MockAnthropicMessage(SAMPLE_TAGS_JSON)
        )

        provider = AnthropicProvider(api_key="test-key")
        tags = await provider.suggest_tags(
            text="Article about ML.",
            summary="Machine learning paper.",
            existing_tags=["ai", "research"],
        )

        assert len(tags) == 2
        assert tags[0].name == "machine-learning"
        assert tags[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_suggest_tags_with_code_block(self, mock_anthropic_client):
        """Test tag suggestion when JSON is in code block."""
        from app.ai.providers.anthropic import AnthropicProvider

        response_with_block = f"```json\n{SAMPLE_TAGS_JSON}\n```"
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=MockAnthropicMessage(response_with_block)
        )

        provider = AnthropicProvider(api_key="test-key")
        tags = await provider.suggest_tags(text="Test")

        assert len(tags) == 2

    @pytest.mark.asyncio
    async def test_suggest_category_success(self, mock_anthropic_client):
        """Test successful category suggestion."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            return_value=MockAnthropicMessage(SAMPLE_CATEGORY_JSON)
        )

        provider = AnthropicProvider(api_key="test-key")
        category = await provider.suggest_category(
            text="Article about deep learning.",
            summary="Neural network paper.",
            categories=[{"name": "AI & ML", "children": []}],
        )

        assert category.category.name == "AI & ML"
        assert category.subcategory.name == "Deep Learning"
        assert category.confidence == 0.88

    @pytest.mark.asyncio
    async def test_answer_question_success(self, mock_anthropic_client):
        """Test successful question answering."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            return_value=MockAnthropicMessage("The transformer uses self-attention.")
        )

        provider = AnthropicProvider(api_key="test-key")
        answer = await provider.answer_question(
            question="What mechanism does the transformer use?",
            context="The transformer architecture uses self-attention.",
        )

        assert "self-attention" in answer.lower()

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_anthropic_client):
        """Test successful health check."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            return_value=MockAnthropicMessage("OK")
        )

        provider = AnthropicProvider(api_key="test-key")
        result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_anthropic_client):
        """Test health check failure."""
        from app.ai.providers.anthropic import AnthropicProvider

        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        provider = AnthropicProvider(api_key="invalid-key")
        result = await provider.health_check()

        assert result is False

    def test_extract_json_simple(self):
        """Test _extract_json with simple JSON."""
        from app.ai.providers.anthropic import AnthropicProvider

        with patch("app.ai.providers.anthropic.AsyncAnthropic"):
            provider = AnthropicProvider(api_key="test")

        result = provider._extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_with_surrounding_text(self):
        """Test _extract_json with text around JSON."""
        from app.ai.providers.anthropic import AnthropicProvider

        with patch("app.ai.providers.anthropic.AsyncAnthropic"):
            provider = AnthropicProvider(api_key="test")

        result = provider._extract_json('Here is the result: {"key": "value"} end')
        assert result == {"key": "value"}

    def test_extract_json_no_json_raises(self):
        """Test _extract_json raises when no JSON found."""
        from app.ai.providers.anthropic import AnthropicProvider

        with patch("app.ai.providers.anthropic.AsyncAnthropic"):
            provider = AnthropicProvider(api_key="test")

        with pytest.raises(ValueError, match="No JSON found"):
            provider._extract_json("This has no JSON")

    def test_models_dict_exists(self):
        """Test that MODELS dict is defined."""
        from app.ai.providers.anthropic import AnthropicProvider

        assert len(AnthropicProvider.MODELS) >= 1
        assert AnthropicProvider.DEFAULT_MODEL in AnthropicProvider.MODELS


# =============================================================================
# OpenAI Provider Tests
# =============================================================================


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch("app.ai.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_init_creates_client(self, mock_openai_client):
        """Test that __init__ creates AsyncOpenAI client."""
        from app.ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")

        assert provider.model_id == OpenAIProvider.DEFAULT_MODEL
        assert provider.provider_name == "openai"

    @pytest.mark.asyncio
    async def test_summarize_success(self, mock_openai_client):
        """Test successful summarization."""
        from app.ai.providers.openai import OpenAIProvider

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MockOpenAIResponse(SAMPLE_MARKDOWN_SUMMARY)
        )

        provider = OpenAIProvider(api_key="test-key")
        summary = await provider.summarize(
            text="Sample article about transformers.",
            title="Test Article",
        )

        assert isinstance(summary, Summary)
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_suggest_tags_success(self, mock_openai_client):
        """Test successful tag suggestion with JSON mode."""
        from app.ai.providers.openai import OpenAIProvider

        # OpenAI returns wrapped JSON due to json_object mode
        wrapped_response = '{"tags": ' + SAMPLE_TAGS_JSON + "}"
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MockOpenAIResponse(wrapped_response)
        )

        provider = OpenAIProvider(api_key="test-key")
        tags = await provider.suggest_tags(text="Test article")

        assert len(tags) == 2
        assert tags[0].name == "machine-learning"

    @pytest.mark.asyncio
    async def test_suggest_tags_unwrapped_array(self, mock_openai_client):
        """Test tag suggestion handles direct array response."""
        from app.ai.providers.openai import OpenAIProvider

        # Sometimes OpenAI might return just the array
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MockOpenAIResponse(SAMPLE_TAGS_JSON)
        )

        provider = OpenAIProvider(api_key="test-key")
        tags = await provider.suggest_tags(text="Test")

        assert len(tags) == 2

    @pytest.mark.asyncio
    async def test_suggest_category_success(self, mock_openai_client):
        """Test successful category suggestion."""
        from app.ai.providers.openai import OpenAIProvider

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MockOpenAIResponse(SAMPLE_CATEGORY_JSON)
        )

        provider = OpenAIProvider(api_key="test-key")
        category = await provider.suggest_category(
            text="Deep learning article.",
            categories=[{"name": "AI & ML", "children": []}],
        )

        assert category.category.name == "AI & ML"
        assert category.confidence == 0.88

    @pytest.mark.asyncio
    async def test_answer_question_success(self, mock_openai_client):
        """Test successful question answering."""
        from app.ai.providers.openai import OpenAIProvider

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MockOpenAIResponse("GPT uses transformer architecture.")
        )

        provider = OpenAIProvider(api_key="test-key")
        answer = await provider.answer_question(
            question="What architecture does GPT use?",
            context="GPT is based on the transformer architecture.",
        )

        assert "transformer" in answer.lower()

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_openai_client):
        """Test successful health check."""
        from app.ai.providers.openai import OpenAIProvider

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MockOpenAIResponse("OK")
        )

        provider = OpenAIProvider(api_key="test-key")
        result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_openai_client):
        """Test health check failure."""
        from app.ai.providers.openai import OpenAIProvider

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        provider = OpenAIProvider(api_key="invalid-key")
        result = await provider.health_check()

        assert result is False

    def test_supports_embeddings(self):
        """Test that OpenAI supports embeddings."""
        from app.ai.providers.openai import OpenAIProvider

        with patch("app.ai.providers.openai.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="test")

        assert provider.supports_embeddings is True

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, mock_openai_client):
        """Test successful embedding generation."""
        from app.ai.providers.openai import OpenAIProvider

        embedding = [0.1] * 1536
        mock_openai_client.embeddings.create = AsyncMock(
            return_value=MockOpenAIEmbeddingResponse(embedding)
        )

        provider = OpenAIProvider(api_key="test-key")
        result = await provider.generate_embedding("Test text")

        assert result == embedding
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_generate_embedding_truncates_long_text(self, mock_openai_client):
        """Test that long text is truncated for embeddings."""
        from app.ai.providers.openai import OpenAIProvider

        embedding = [0.1] * 1536
        mock_openai_client.embeddings.create = AsyncMock(
            return_value=MockOpenAIEmbeddingResponse(embedding)
        )

        provider = OpenAIProvider(api_key="test-key")
        long_text = "x" * 100000  # Very long text
        await provider.generate_embedding(long_text)

        # Check that the text was truncated
        call_args = mock_openai_client.embeddings.create.call_args
        sent_text = call_args.kwargs["input"]
        assert len(sent_text) <= provider.EMBEDDING_MAX_TOKENS * 4

    @pytest.mark.asyncio
    async def test_generate_embedding_error_returns_none(self, mock_openai_client):
        """Test that embedding errors return None."""
        from app.ai.providers.openai import OpenAIProvider

        mock_openai_client.embeddings.create = AsyncMock(
            side_effect=Exception("Embedding error")
        )

        provider = OpenAIProvider(api_key="test-key")
        result = await provider.generate_embedding("Test")

        assert result is None

    def test_models_dict_exists(self):
        """Test that MODELS dict is defined."""
        from app.ai.providers.openai import OpenAIProvider

        assert len(OpenAIProvider.MODELS) >= 1
        assert OpenAIProvider.DEFAULT_MODEL in OpenAIProvider.MODELS


# =============================================================================
# Google Provider Tests
# =============================================================================


class TestGoogleProvider:
    """Tests for GoogleProvider."""

    @pytest.fixture
    def mock_google_genai(self):
        """Create a mock Google genai module."""
        with patch("app.ai.providers.google.genai") as mock_genai:
            mock_model = AsyncMock()
            mock_genai.GenerativeModel.return_value = mock_model
            yield mock_genai, mock_model

    @pytest.mark.asyncio
    async def test_init_configures_api(self, mock_google_genai):
        """Test that __init__ configures Google API."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key="test-key")

        mock_genai.configure.assert_called_once_with(api_key="test-key")
        assert provider.model_id == GoogleProvider.DEFAULT_MODEL
        assert provider.provider_name == "google"

    @pytest.mark.asyncio
    async def test_init_with_custom_model(self, mock_google_genai):
        """Test init with custom model."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key="test-key", model_id="gemini-3.0-flash")

        assert provider.model_id == "gemini-3.0-flash"

    @pytest.mark.asyncio
    async def test_summarize_success(self, mock_google_genai):
        """Test successful summarization."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            return_value=MockGeminiResponse(SAMPLE_MARKDOWN_SUMMARY)
        )

        provider = GoogleProvider(api_key="test-key")
        summary = await provider.summarize(
            text="Sample article about transformers.",
            title="Test Article",
        )

        assert isinstance(summary, Summary)
        mock_model.generate_content_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_error_propagates(self, mock_google_genai):
        """Test that summarize errors are propagated."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            side_effect=Exception("API Error")
        )

        provider = GoogleProvider(api_key="test-key")

        with pytest.raises(Exception, match="API Error"):
            await provider.summarize(text="Test")

    @pytest.mark.asyncio
    async def test_suggest_tags_success(self, mock_google_genai):
        """Test successful tag suggestion."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            return_value=MockGeminiResponse(SAMPLE_TAGS_JSON)
        )

        provider = GoogleProvider(api_key="test-key")
        tags = await provider.suggest_tags(
            text="Article about ML.",
            existing_tags=["ai"],
        )

        assert len(tags) == 2
        assert tags[0].name == "machine-learning"

    @pytest.mark.asyncio
    async def test_suggest_category_success(self, mock_google_genai):
        """Test successful category suggestion."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            return_value=MockGeminiResponse(SAMPLE_CATEGORY_JSON)
        )

        provider = GoogleProvider(api_key="test-key")
        category = await provider.suggest_category(
            text="Deep learning article.",
            categories=[{"name": "AI & ML", "children": []}],
        )

        assert category.category.name == "AI & ML"
        assert category.subcategory.name == "Deep Learning"

    @pytest.mark.asyncio
    async def test_answer_question_success(self, mock_google_genai):
        """Test successful question answering."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            return_value=MockGeminiResponse("Gemini uses transformer architecture.")
        )

        provider = GoogleProvider(api_key="test-key")
        answer = await provider.answer_question(
            question="What architecture does Gemini use?",
            context="Gemini is based on transformers.",
        )

        assert "transformer" in answer.lower()

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_google_genai):
        """Test successful health check."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            return_value=MockGeminiResponse("OK")
        )

        provider = GoogleProvider(api_key="test-key")
        result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_google_genai):
        """Test health check failure."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        mock_model.generate_content_async = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        provider = GoogleProvider(api_key="invalid-key")
        result = await provider.health_check()

        assert result is False

    def test_extract_json_simple(self, mock_google_genai):
        """Test _extract_json with simple JSON."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key="test")

        result = provider._extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_array(self, mock_google_genai):
        """Test _extract_json with JSON array."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key="test")

        result = provider._extract_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_extract_json_with_code_block(self, mock_google_genai):
        """Test _extract_json with markdown code block."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key="test")

        result = provider._extract_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_extract_json_no_json_raises(self, mock_google_genai):
        """Test _extract_json raises when no JSON found."""
        mock_genai, mock_model = mock_google_genai
        from app.ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key="test")

        with pytest.raises(ValueError, match="No JSON found"):
            provider._extract_json("Plain text without JSON")

    def test_models_dict_exists(self):
        """Test that MODELS dict is defined."""
        from app.ai.providers.google import GoogleProvider

        assert len(GoogleProvider.MODELS) >= 1
        assert GoogleProvider.DEFAULT_MODEL in GoogleProvider.MODELS


# =============================================================================
# Cross-Provider Tests
# =============================================================================


class TestProviderConsistency:
    """Tests that verify consistency across all providers."""

    def test_all_providers_have_provider_name(self):
        """Test that all providers have provider_name attribute."""
        from app.ai.providers.anthropic import AnthropicProvider
        from app.ai.providers.google import GoogleProvider
        from app.ai.providers.openai import OpenAIProvider

        assert AnthropicProvider.provider_name == "anthropic"
        assert OpenAIProvider.provider_name == "openai"
        assert GoogleProvider.provider_name == "google"

    def test_all_providers_have_models_dict(self):
        """Test that all providers have MODELS dict."""
        from app.ai.providers.anthropic import AnthropicProvider
        from app.ai.providers.google import GoogleProvider
        from app.ai.providers.openai import OpenAIProvider

        for provider_cls in [AnthropicProvider, OpenAIProvider, GoogleProvider]:
            assert hasattr(provider_cls, "MODELS")
            assert isinstance(provider_cls.MODELS, dict)
            assert len(provider_cls.MODELS) > 0

    def test_all_providers_have_default_model(self):
        """Test that all providers have DEFAULT_MODEL."""
        from app.ai.providers.anthropic import AnthropicProvider
        from app.ai.providers.google import GoogleProvider
        from app.ai.providers.openai import OpenAIProvider

        for provider_cls in [AnthropicProvider, OpenAIProvider, GoogleProvider]:
            assert hasattr(provider_cls, "DEFAULT_MODEL")
            assert provider_cls.DEFAULT_MODEL in provider_cls.MODELS
