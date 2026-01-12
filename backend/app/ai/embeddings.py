"""
Local embedding service using sentence-transformers.

This runs entirely locally via sentence-transformers - no API key needed.
The model is downloaded from Hugging Face on first use (~420MB).

Uses all-mpnet-base-v2, a high-quality general-purpose embedding model
that produces 768-dimensional vectors optimized for semantic search.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global model instance - loaded once at first use
_embedding_model = None

# Model configuration
# all-mpnet-base-v2 is one of the best general-purpose models:
# - 768 dimensions (same as EmbeddingGemma)
# - Excellent quality for semantic search
# - No authentication required (not a gated model)
MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIM = 768
MAX_CHARS = 8000  # ~2K tokens, safe limit for the model


def get_embedding_model():
    """
    Get or initialize the embedding model.

    The model is loaded once and cached globally.
    First call will download ~600MB from Hugging Face.
    """
    global _embedding_model

    if _embedding_model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(MODEL_NAME)
            logger.info(f"Embedding model loaded successfully (dim={EMBEDDING_DIM})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    return _embedding_model


def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate embedding for document/article text.

    Uses model.encode() for documents (vs encode_query for search queries).
    This asymmetry is intentional - the model is trained this way.

    Args:
        text: The document text to embed

    Returns:
        768-dimensional embedding vector, or None on error
    """
    if not text or not text.strip():
        return None

    try:
        model = get_embedding_model()

        # Truncate to safe length
        truncated = text[:MAX_CHARS]

        # Generate embedding with normalization
        embedding = model.encode(truncated, normalize_embeddings=True)

        return embedding.tolist()

    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


def generate_query_embedding(query: str) -> Optional[list[float]]:
    """
    Generate embedding for a search query.

    Uses model.encode_query() which is optimized for queries.
    This is different from document embedding - the model is trained
    with asymmetric encoding for better retrieval.

    Args:
        query: The search query

    Returns:
        768-dimensional embedding vector, or None on error
    """
    if not query or not query.strip():
        return None

    try:
        model = get_embedding_model()

        # Queries are typically short, but truncate anyway
        truncated = query[:MAX_CHARS]

        # Use encode_query for search queries
        # Falls back to regular encode if model doesn't have encode_query
        if hasattr(model, 'encode_query'):
            embedding = model.encode_query(truncated)
        else:
            embedding = model.encode(truncated, normalize_embeddings=True)

        return embedding.tolist()

    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        return None


def is_model_available() -> bool:
    """Check if the embedding model can be loaded."""
    try:
        get_embedding_model()
        return True
    except Exception:
        return False
