"""
Test script for AI providers.

This script tests the AI summarization, tagging, and categorization features.
Requires a valid API key to be set in environment variables.

Run with: python tests/test_ai.py

Environment variables:
  ANTHROPIC_API_KEY - For testing Claude
  OPENAI_API_KEY - For testing OpenAI
  GOOGLE_API_KEY - For testing Gemini
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Sample article text for testing
SAMPLE_ARTICLE = """
Attention Is All You Need

Abstract:
The dominant sequence transduction models are based on complex recurrent or
convolutional neural networks that include an encoder and a decoder. The best
performing models also connect the encoder and decoder through an attention
mechanism. We propose a new simple network architecture, the Transformer,
based solely on attention mechanisms, dispensing with recurrence and convolutions
entirely. Experiments on two machine translation tasks show these models to
be superior in quality while being more parallelizable and requiring significantly
less time to train.

1. Introduction
Recurrent neural networks, long short-term memory and gated recurrent neural networks
in particular, have been firmly established as state of the art approaches in sequence
modeling and transduction problems such as language modeling and machine translation.
Numerous efforts have since continued to push the boundaries of recurrent language
models and encoder-decoder architectures.

Recurrent models typically factor computation along the symbol positions of the input
and output sequences. Aligning the positions to steps in computation time, they generate
a sequence of hidden states ht, as a function of the previous hidden state ht−1 and
the input for position t. This inherently sequential nature precludes parallelization
within training examples, which becomes critical at longer sequence lengths, as memory
constraints limit batching across examples.

The Transformer allows for significantly more parallelization and can reach a new
state of the art in translation quality after being trained for as little as twelve
hours on eight P100 GPUs.

2. Model Architecture
The Transformer follows an encoder-decoder structure using stacked self-attention
and point-wise, fully connected layers for both the encoder and decoder.

3. Why Self-Attention
Self-attention, sometimes called intra-attention is an attention mechanism relating
different positions of a single sequence in order to compute a representation of
the sequence. Self-attention has been used successfully in a variety of tasks
including reading comprehension, abstractive summarization, textual entailment
and learning task-independent sentence representations.

4. Conclusion
In this work, we presented the Transformer, the first sequence transduction model
based entirely on attention, replacing the recurrent layers most commonly used in
encoder-decoder architectures with multi-headed self-attention.

The Transformer can be trained significantly faster than architectures based on
recurrent or convolutional layers. We achieved a new state of the art on English-to-German
and English-to-French translation tasks.
"""

SAMPLE_CATEGORIES = [
    {
        "name": "AI & Machine Learning",
        "children": [
            {"name": "Safety", "children": []},
            {"name": "Capabilities", "children": []},
            {"name": "Governance/Policy", "children": []},
        ],
    },
    {"name": "Economics", "children": []},
    {"name": "Philosophy", "children": []},
    {"name": "Policy & Regulation", "children": []},
    {"name": "Technical/Engineering", "children": []},
]


async def test_anthropic_provider():
    """Test Anthropic Claude provider"""
    print("\n" + "=" * 60)
    print("TEST: Anthropic Claude Provider")
    print("=" * 60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[SKIP] ANTHROPIC_API_KEY not set")
        return None

    from app.ai.providers.anthropic import AnthropicProvider

    try:
        provider = AnthropicProvider(api_key=api_key)

        # Test health check
        print("\n1. Testing health check...")
        healthy = await provider.health_check()
        print(f"   Health check: {'PASS' if healthy else 'FAIL'}")

        if not healthy:
            return False

        # Test summarization
        print("\n2. Testing summarization...")
        summary = await provider.summarize(
            text=SAMPLE_ARTICLE,
            title="Attention Is All You Need",
            source_type="arxiv",
        )

        print(f"\n   Title: {summary.title_suggestion}")
        print(f"   Abstract: {summary.abstract[:200]}...")
        print(f"   Key contributions: {len(summary.key_contributions)} points")
        print(f"   Findings: {len(summary.findings)} points")
        print(f"   Relevance: {summary.relevance_note[:100]}...")

        # Test tag suggestion
        print("\n3. Testing tag suggestions...")
        tags = await provider.suggest_tags(
            text=SAMPLE_ARTICLE,
            summary=summary.abstract,
            existing_tags=["machine-learning", "nlp", "deep-learning"],
        )

        print(f"   Suggested {len(tags)} tags:")
        for tag in tags[:5]:
            print(f"   - {tag.name} (confidence: {tag.confidence:.2f})")

        # Test category suggestion
        print("\n4. Testing category suggestion...")
        category = await provider.suggest_category(
            text=SAMPLE_ARTICLE,
            summary=summary.abstract,
            categories=SAMPLE_CATEGORIES,
        )

        print(f"   Category: {category.category_name}")
        print(f"   Parent: {category.parent_category}")
        print(f"   Confidence: {category.confidence:.2f}")
        print(f"   Reasoning: {category.reasoning[:100]}...")

        print("\n[PASS] Anthropic provider tests completed!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Anthropic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_openai_provider():
    """Test OpenAI GPT provider"""
    print("\n" + "=" * 60)
    print("TEST: OpenAI GPT Provider")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[SKIP] OPENAI_API_KEY not set")
        return None

    from app.ai.providers.openai import OpenAIProvider

    try:
        provider = OpenAIProvider(api_key=api_key)

        # Test health check
        print("\n1. Testing health check...")
        healthy = await provider.health_check()
        print(f"   Health check: {'PASS' if healthy else 'FAIL'}")

        if not healthy:
            return False

        # Test summarization
        print("\n2. Testing summarization...")
        summary = await provider.summarize(
            text=SAMPLE_ARTICLE,
            title="Attention Is All You Need",
            source_type="arxiv",
        )

        print(f"\n   Title: {summary.title_suggestion}")
        print(f"   Abstract: {summary.abstract[:200]}...")
        print(f"   Key contributions: {len(summary.key_contributions)} points")

        print("\n[PASS] OpenAI provider tests completed!")
        return True

    except Exception as e:
        print(f"\n[FAIL] OpenAI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_google_provider():
    """Test Google Gemini provider"""
    print("\n" + "=" * 60)
    print("TEST: Google Gemini Provider")
    print("=" * 60)

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[SKIP] GOOGLE_API_KEY not set")
        return None

    from app.ai.providers.google import GoogleProvider

    try:
        provider = GoogleProvider(api_key=api_key)

        # Test health check
        print("\n1. Testing health check...")
        healthy = await provider.health_check()
        print(f"   Health check: {'PASS' if healthy else 'FAIL'}")

        if not healthy:
            return False

        # Test summarization
        print("\n2. Testing summarization...")
        summary = await provider.summarize(
            text=SAMPLE_ARTICLE,
            title="Attention Is All You Need",
            source_type="arxiv",
        )

        print(f"\n   Title: {summary.title_suggestion}")
        print(f"   Abstract: {summary.abstract[:200]}...")
        print(f"   Key contributions: {len(summary.key_contributions)} points")

        print("\n[PASS] Google provider tests completed!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Google test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_encryption():
    """Test API key encryption utilities"""
    print("\n" + "=" * 60)
    print("TEST: Encryption Utilities")
    print("=" * 60)

    # Set a test encryption key
    os.environ["ENCRYPTION_KEY"] = "test-encryption-key-for-unit-tests"

    # Clear the cache to use new key
    from app.utils.encryption import get_fernet, encrypt_api_key, decrypt_api_key, mask_api_key
    get_fernet.cache_clear()

    try:
        test_key = "sk-test-api-key-12345678901234567890"

        # Test encryption/decryption
        print("\n1. Testing encryption/decryption...")
        encrypted = encrypt_api_key(test_key)
        decrypted = decrypt_api_key(encrypted)

        assert decrypted == test_key, "Decrypted key doesn't match original"
        print("   Encryption/decryption: PASS")

        # Test masking
        print("\n2. Testing key masking...")
        masked = mask_api_key(test_key)
        print(f"   Original: {test_key}")
        print(f"   Masked: {masked}")
        assert "..." in masked, "Masked key should contain ellipsis"
        assert masked.endswith(test_key[-4:]), "Masked key should end with last 4 chars"
        print("   Masking: PASS")

        print("\n[PASS] Encryption tests completed!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Encryption test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all AI tests"""
    print("\n" + "#" * 60)
    print("# Alexandria AI Provider Tests")
    print("#" * 60)

    results = {
        "Encryption": await test_encryption(),
        "Anthropic": await test_anthropic_provider(),
        "OpenAI": await test_openai_provider(),
        "Google": await test_google_provider(),
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        if result is None:
            status = "[SKIP]"
        elif result:
            status = "[PASS]"
        else:
            status = "[FAIL]"
        print(f"{status} {test_name}")

    # Count only non-skipped tests
    run_tests = {k: v for k, v in results.items() if v is not None}
    passed = sum(1 for v in run_tests.values() if v)
    total = len(run_tests)

    print(f"\nTotal: {passed}/{total} tests passed ({len(results) - total} skipped)")

    return all(v for v in run_tests.values())


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
