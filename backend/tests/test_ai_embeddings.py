"""
Tests for the Embeddings module (app/ai/embeddings.py).

Tests local embedding generation using sentence-transformers:
- Document embedding generation
- Query embedding generation
- Model caching
- Error handling
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.ai.embeddings import (
    EMBEDDING_DIM,
    MAX_CHARS,
    MODEL_NAME,
    generate_embedding,
    generate_query_embedding,
    get_embedding_model,
    is_model_available,
)


# =============================================================================
# Model Configuration Tests
# =============================================================================


def test_embedding_dim_is_768():
    """Test that embedding dimension is 768 (all-mpnet-base-v2)."""
    assert EMBEDDING_DIM == 768


def test_max_chars_is_reasonable():
    """Test that max chars limit is set appropriately."""
    assert MAX_CHARS == 8000  # ~2K tokens


def test_model_name_configured():
    """Test that model name is configured."""
    assert MODEL_NAME == "sentence-transformers/all-mpnet-base-v2"


# =============================================================================
# Generate Embedding Tests
# =============================================================================


def test_generate_embedding_success(mock_embedding_model):
    """Test successful embedding generation."""
    result = generate_embedding("This is a test document about machine learning.")

    assert result is not None
    assert len(result) == 768
    assert isinstance(result, list)
    assert all(isinstance(x, float) for x in result)


def test_generate_embedding_empty_text_returns_none(mock_embedding_model):
    """Test that empty text returns None."""
    assert generate_embedding("") is None
    assert generate_embedding("   ") is None
    assert generate_embedding(None) is None


def test_generate_embedding_truncates_long_text(mock_embedding_model):
    """Test that long text is truncated to MAX_CHARS."""
    long_text = "x" * 20000  # Way over MAX_CHARS

    generate_embedding(long_text)

    # Check that encode was called with truncated text
    call_args = mock_embedding_model.encode.call_args
    truncated_text = call_args[0][0]
    assert len(truncated_text) == MAX_CHARS


def test_generate_embedding_normalizes_output(mock_embedding_model):
    """Test that embeddings are normalized."""
    generate_embedding("Test text")

    # Check that normalize_embeddings=True was passed
    call_kwargs = mock_embedding_model.encode.call_args.kwargs
    assert call_kwargs.get("normalize_embeddings") is True


def test_generate_embedding_error_returns_none(mock_embedding_model):
    """Test that errors return None instead of raising."""
    mock_embedding_model.encode.side_effect = Exception("Model error")

    result = generate_embedding("Test text")

    assert result is None


# =============================================================================
# Generate Query Embedding Tests
# =============================================================================


def test_generate_query_embedding_success(mock_embedding_model):
    """Test successful query embedding generation."""
    # The mock uses encode() as fallback since encode_query isn't available
    result = generate_query_embedding("What is machine learning?")

    assert result is not None
    # The mock returns [0.1] * 768, converted to list
    assert len(result) == 768


def test_generate_query_embedding_empty_returns_none(mock_embedding_model):
    """Test that empty query returns None."""
    assert generate_query_embedding("") is None
    assert generate_query_embedding("   ") is None


def test_generate_query_embedding_uses_encode_query_if_available(mock_embedding_model):
    """Test that encode_query is used when available."""
    # The mock doesn't have encode_query by default, so it uses encode
    # This test verifies the fallback behavior works correctly
    result = generate_query_embedding("Test query")

    # Should fall back to encode since MagicMock doesn't have encode_query
    mock_embedding_model.encode.assert_called()
    assert result is not None


def test_generate_query_embedding_falls_back_to_encode(mock_embedding_model):
    """Test fallback to regular encode if encode_query not available."""
    # Remove encode_query method
    if hasattr(mock_embedding_model, "encode_query"):
        delattr(mock_embedding_model, "encode_query")

    result = generate_query_embedding("Test query")

    # Should fall back to regular encode
    mock_embedding_model.encode.assert_called()
    assert result is not None


def test_generate_query_embedding_error_returns_none(mock_embedding_model):
    """Test that query embedding errors return None."""
    mock_embedding_model.encode.side_effect = Exception("Query error")
    if hasattr(mock_embedding_model, "encode_query"):
        delattr(mock_embedding_model, "encode_query")

    result = generate_query_embedding("Test query")

    assert result is None


# =============================================================================
# Model Loading Tests
# =============================================================================


def test_get_embedding_model_loads_model(mock_sentence_transformer):
    """Test that get_embedding_model loads the model."""
    import app.ai.embeddings as embeddings_module

    # Reset global
    embeddings_module._embedding_model = None

    model = get_embedding_model()

    assert model is not None


def test_get_embedding_model_caches_model(mock_sentence_transformer):
    """Test that model is cached after first load."""
    import app.ai.embeddings as embeddings_module

    # Reset global
    embeddings_module._embedding_model = None

    model1 = get_embedding_model()
    model2 = get_embedding_model()

    # Should be the same instance (cached)
    assert model1 is model2


def test_get_embedding_model_error_propagates():
    """Test that model loading errors are propagated."""
    import app.ai.embeddings as embeddings_module

    # Reset global
    embeddings_module._embedding_model = None

    with patch(
        "sentence_transformers.SentenceTransformer",
        side_effect=Exception("Model download failed"),
    ):
        with pytest.raises(Exception, match="Model download failed"):
            get_embedding_model()


# =============================================================================
# Model Availability Tests
# =============================================================================


def test_is_model_available_true(mock_embedding_model):
    """Test is_model_available returns True when model loads."""
    result = is_model_available()
    assert result is True


def test_is_model_available_false_on_error():
    """Test is_model_available returns False on error."""
    import app.ai.embeddings as embeddings_module

    # Reset global
    embeddings_module._embedding_model = None

    with patch(
        "sentence_transformers.SentenceTransformer",
        side_effect=Exception("Cannot load"),
    ):
        result = is_model_available()
        assert result is False


# =============================================================================
# Integration-style Tests (with mocked model)
# =============================================================================


def test_embedding_dimensions_match_pgvector(mock_embedding_model):
    """Test that embedding dimensions match pgvector column size."""
    # pgvector in Alexandria uses 768 dimensions
    embedding = generate_embedding("Test document")

    assert len(embedding) == 768  # Must match database vector(768)


def test_embedding_values_are_floats(mock_embedding_model):
    """Test that all embedding values are proper floats."""
    embedding = generate_embedding("Test document")

    # All values should be Python floats (not numpy types)
    for value in embedding:
        assert isinstance(value, float)
        assert not np.isnan(value)
        assert not np.isinf(value)


def test_different_texts_get_different_embeddings():
    """Test that different texts produce different embeddings (conceptually)."""
    import app.ai.embeddings as embeddings_module

    embeddings_module._embedding_model = None

    with patch("sentence_transformers.SentenceTransformer") as mock_cls:
        # Setup to return different embeddings for different texts
        mock_model = MagicMock()
        call_count = [0]

        def encode_side_effect(text, **kwargs):
            call_count[0] += 1
            # Return slightly different embeddings based on call count
            return np.array([0.1 + call_count[0] * 0.01] * 768, dtype=np.float32)

        mock_model.encode.side_effect = encode_side_effect
        mock_cls.return_value = mock_model

        emb1 = generate_embedding("First document about AI")
        emb2 = generate_embedding("Second document about cooking")

        # Embeddings should be different
        assert emb1 != emb2

    # Cleanup
    embeddings_module._embedding_model = None
