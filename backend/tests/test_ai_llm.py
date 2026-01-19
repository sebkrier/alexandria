"""
Tests for the LiteLLM wrapper (app/ai/llm.py).

Tests the unified LiteLLM interface for all AI providers:
- Model name formatting for different providers
- Response parsing (JSON extraction)
- Error handling
- Provider configuration
"""


import pytest

from app.ai.llm import (
    PROVIDER_MODELS,
    PROVIDER_PREFIXES,
    LiteLLMProvider,
    _extract_json,
    complete,
)

# =============================================================================
# Provider Configuration Tests
# =============================================================================


def test_provider_models_configured():
    """Test that all providers have models defined."""
    assert "anthropic" in PROVIDER_MODELS
    assert "openai" in PROVIDER_MODELS
    assert "google" in PROVIDER_MODELS

    # Each provider should have at least one model
    for provider, models in PROVIDER_MODELS.items():
        assert len(models) > 0, f"{provider} has no models configured"


def test_provider_prefixes_defined():
    """Test that provider prefixes are correctly defined."""
    assert PROVIDER_PREFIXES["anthropic"] == "anthropic/"
    assert PROVIDER_PREFIXES["openai"] == ""  # No prefix for OpenAI
    assert PROVIDER_PREFIXES["google"] == "gemini/"


def test_anthropic_models_have_claude_prefix():
    """Test Anthropic models are correctly named."""
    for model_id in PROVIDER_MODELS["anthropic"]:
        assert "claude" in model_id.lower()


def test_openai_models_have_gpt_or_o_prefix():
    """Test OpenAI models are correctly named."""
    for model_id in PROVIDER_MODELS["openai"]:
        assert model_id.startswith(("gpt-", "o"))


def test_google_models_have_gemini_prefix():
    """Test Google models are correctly named."""
    for model_id in PROVIDER_MODELS["google"]:
        assert "gemini" in model_id.lower()


# =============================================================================
# Model Name Formatting Tests
# =============================================================================


@pytest.mark.asyncio
async def test_complete_anthropic_format(mock_litellm):
    """Test that Anthropic models are formatted with anthropic/ prefix."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse("Response")

    await complete(
        messages=[{"role": "user", "content": "Hi"}],
        api_key="test-key",
        model="claude-sonnet-4-20250514",
        provider="anthropic",
    )

    # Check the model name passed to litellm
    mock_litellm.assert_called_once()
    call_kwargs = mock_litellm.call_args.kwargs
    assert call_kwargs["model"] == "anthropic/claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_complete_openai_format(mock_litellm):
    """Test that OpenAI models have no prefix."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse("Response")

    await complete(
        messages=[{"role": "user", "content": "Hi"}],
        api_key="test-key",
        model="gpt-4.1",
        provider="openai",
    )

    call_kwargs = mock_litellm.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4.1"  # No prefix


@pytest.mark.asyncio
async def test_complete_google_format(mock_litellm):
    """Test that Google models are formatted with gemini/ prefix."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse("Response")

    await complete(
        messages=[{"role": "user", "content": "Hi"}],
        api_key="test-key",
        model="gemini-2.5-flash",
        provider="google",
    )

    call_kwargs = mock_litellm.call_args.kwargs
    assert call_kwargs["model"] == "gemini/gemini-2.5-flash"


@pytest.mark.asyncio
async def test_complete_passes_api_key(mock_litellm):
    """Test that API key is passed to LiteLLM."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse("Response")

    await complete(
        messages=[{"role": "user", "content": "Hi"}],
        api_key="sk-secret-key",
        model="gpt-4.1",
        provider="openai",
    )

    call_kwargs = mock_litellm.call_args.kwargs
    assert call_kwargs["api_key"] == "sk-secret-key"


@pytest.mark.asyncio
async def test_complete_passes_temperature_and_max_tokens(mock_litellm):
    """Test that temperature and max_tokens are passed correctly."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse("Response")

    await complete(
        messages=[{"role": "user", "content": "Hi"}],
        api_key="test-key",
        model="gpt-4.1",
        provider="openai",
        temperature=0.7,
        max_tokens=500,
    )

    call_kwargs = mock_litellm.call_args.kwargs
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 500


# =============================================================================
# JSON Extraction Tests
# =============================================================================


def test_extract_json_simple_object():
    """Test extracting JSON object from text."""
    text = '{"name": "test", "value": 123}'
    result = _extract_json(text)
    assert result == {"name": "test", "value": 123}


def test_extract_json_simple_array():
    """Test extracting JSON array from text."""
    text = '[1, 2, 3]'
    result = _extract_json(text)
    assert result == [1, 2, 3]


def test_extract_json_with_markdown_code_block():
    """Test extracting JSON from markdown code block."""
    text = """Here's the result:
```json
{"status": "success"}
```
"""
    result = _extract_json(text)
    assert result == {"status": "success"}


def test_extract_json_with_surrounding_text():
    """Test extracting JSON when surrounded by text."""
    text = """The analysis shows:
{"confidence": 0.9, "reasoning": "Based on content"}
That's my assessment."""
    result = _extract_json(text)
    assert result["confidence"] == 0.9


def test_extract_json_nested_objects():
    """Test extracting nested JSON structures."""
    text = '{"outer": {"inner": {"value": 42}}}'
    result = _extract_json(text)
    assert result["outer"]["inner"]["value"] == 42


def test_extract_json_no_json_raises():
    """Test that missing JSON raises ValueError."""
    text = "This is just plain text with no JSON"
    with pytest.raises(ValueError, match="No JSON found"):
        _extract_json(text)


def test_extract_json_array_of_objects():
    """Test extracting array of objects (for tags)."""
    text = """
[
    {"name": "tag1", "confidence": 0.9},
    {"name": "tag2", "confidence": 0.8}
]
"""
    result = _extract_json(text)
    assert len(result) == 2
    assert result[0]["name"] == "tag1"


# =============================================================================
# LiteLLMProvider Tests
# =============================================================================


@pytest.mark.asyncio
async def test_provider_summarize(mock_litellm, sample_summary_markdown):
    """Test LiteLLMProvider summarize method."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse(sample_summary_markdown)

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    summary = await provider.summarize(
        text="Sample article text about transformers.",
        title="Test Article",
        source_type="url",
    )

    assert summary is not None
    assert summary.markdown == sample_summary_markdown
    assert "machine learning transformers" in summary.abstract.lower()


@pytest.mark.asyncio
async def test_provider_suggest_tags(mock_litellm, sample_tags_json):
    """Test LiteLLMProvider suggest_tags method."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse(sample_tags_json)

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    tags = await provider.suggest_tags(
        text="Sample article text.",
        summary="Article about ML.",
        existing_tags=["ai", "research"],
    )

    assert len(tags) == 3
    assert tags[0].name == "machine-learning"
    assert tags[0].confidence == 0.95


@pytest.mark.asyncio
async def test_provider_suggest_category(mock_litellm, sample_category_json):
    """Test LiteLLMProvider suggest_category method."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse(sample_category_json)

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    category = await provider.suggest_category(
        text="Sample article text.",
        summary="Article about ML.",
        categories=[{"name": "AI & Machine Learning", "children": []}],
    )

    assert category.category.name == "AI & Machine Learning"
    assert category.subcategory.name == "Deep Learning"
    assert category.confidence == 0.88


@pytest.mark.asyncio
async def test_provider_answer_question(mock_litellm):
    """Test LiteLLMProvider answer_question method."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse(
        "The Transformer model uses self-attention mechanisms."
    )

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    answer = await provider.answer_question(
        question="What mechanism does the Transformer use?",
        context="The Transformer architecture uses self-attention.",
    )

    assert "self-attention" in answer.lower()


@pytest.mark.asyncio
async def test_provider_health_check_success(mock_litellm):
    """Test LiteLLMProvider health_check returns True on success."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse("OK")

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    result = await provider.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_provider_health_check_failure(mock_litellm):
    """Test LiteLLMProvider health_check returns False on error."""
    mock_litellm.side_effect = Exception("Invalid API key")

    provider = LiteLLMProvider(
        api_key="invalid-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    result = await provider.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_provider_extract_metadata(mock_litellm):
    """Test LiteLLMProvider extract_metadata method."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse(
        '{"title": "Attention Is All You Need", "authors": ["Vaswani et al."]}'
    )

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    metadata = await provider.extract_metadata(
        text="Attention Is All You Need by Vaswani et al."
    )

    assert metadata.title == "Attention Is All You Need"
    assert "Vaswani et al." in metadata.authors


@pytest.mark.asyncio
async def test_provider_extract_metadata_error_fallback(mock_litellm):
    """Test extract_metadata returns empty metadata on error."""
    mock_litellm.side_effect = Exception("API error")

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    metadata = await provider.extract_metadata(text="Some text")

    # Should return default metadata, not raise
    assert metadata.title == "Untitled"
    assert metadata.authors == []


@pytest.mark.asyncio
async def test_provider_name_property():
    """Test provider_name property returns correct value."""
    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="gpt-4.1",
        provider_name="openai",
    )

    assert provider.provider_name == "openai"


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_complete_error_handling(mock_litellm):
    """Test that API errors are propagated."""
    mock_litellm.side_effect = Exception("Rate limit exceeded")

    with pytest.raises(Exception, match="Rate limit"):
        await complete(
            messages=[{"role": "user", "content": "Hi"}],
            api_key="test-key",
            model="gpt-4.1",
            provider="openai",
        )


@pytest.mark.asyncio
async def test_provider_summarize_error(mock_litellm):
    """Test that summarize errors are propagated."""
    mock_litellm.side_effect = Exception("Context length exceeded")

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    with pytest.raises(Exception, match="Context length"):
        await provider.summarize(text="Very long text" * 10000)


@pytest.mark.asyncio
async def test_provider_suggest_tags_error(mock_litellm):
    """Test that suggest_tags errors are propagated."""
    mock_litellm.side_effect = Exception("Invalid request")

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    with pytest.raises(Exception, match="Invalid request"):
        await provider.suggest_tags(text="Sample text")


@pytest.mark.asyncio
async def test_provider_suggest_category_error(mock_litellm):
    """Test that suggest_category errors are propagated."""
    mock_litellm.side_effect = Exception("Timeout")

    provider = LiteLLMProvider(
        api_key="test-key",
        model_id="claude-sonnet-4-20250514",
        provider_name="anthropic",
    )

    with pytest.raises(Exception, match="Timeout"):
        await provider.suggest_category(text="Sample text")
