"""
Test script for content extractors.

Run with: pytest tests/test_extractors.py -v

Or run directly: python tests/test_extractors.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.extractors import extract_content, URLExtractor, ArxivExtractor
from app.extractors.base import ExtractedContent


async def test_url_extraction():
    """Test extraction from a general web URL"""
    print("\n" + "=" * 60)
    print("TEST 1: URL Extraction (Web Article)")
    print("=" * 60)

    # Using a stable, well-structured article
    url = "https://www.paulgraham.com/startupideas.html"

    try:
        content = await extract_content(url=url)

        print(f"\nSource Type: {content.source_type}")
        print(f"Title: {content.title}")
        print(f"Authors: {content.authors}")
        print(f"URL: {content.original_url}")
        print(f"Text Length: {len(content.text)} characters")
        print(f"Text Preview: {content.text[:500]}...")

        # Assertions
        assert content.source_type == "url"
        assert content.title is not None and len(content.title) > 0
        assert content.text is not None and len(content.text) > 100

        print("\n[PASS] URL extraction successful!")
        return True

    except Exception as e:
        print(f"\n[FAIL] URL extraction failed: {e}")
        return False


async def test_arxiv_extraction():
    """Test extraction from an arXiv paper"""
    print("\n" + "=" * 60)
    print("TEST 2: ArXiv Extraction")
    print("=" * 60)

    # Using a well-known paper (Attention Is All You Need)
    url = "https://arxiv.org/abs/1706.03762"

    try:
        content = await extract_content(url=url)

        print(f"\nSource Type: {content.source_type}")
        print(f"Title: {content.title}")
        print(f"Authors: {content.authors[:3]}..." if len(content.authors) > 3 else f"Authors: {content.authors}")
        print(f"Publication Date: {content.publication_date}")
        print(f"ArXiv ID: {content.metadata.get('arxiv_id')}")
        print(f"Categories: {content.metadata.get('categories')}")
        print(f"Text Length: {len(content.text)} characters")
        print(f"Abstract: {content.metadata.get('abstract', '')[:300]}...")

        # Assertions
        assert content.source_type == "arxiv"
        assert "attention" in content.title.lower() or "transformer" in content.title.lower()
        assert len(content.authors) > 0
        assert content.metadata.get("arxiv_id") == "1706.03762"
        assert content.text is not None and len(content.text) > 1000

        print("\n[PASS] ArXiv extraction successful!")
        return True

    except Exception as e:
        print(f"\n[FAIL] ArXiv extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_pdf_extraction():
    """Test extraction from a local PDF file"""
    print("\n" + "=" * 60)
    print("TEST 3: PDF Extraction")
    print("=" * 60)

    # For this test, we'll create a simple test PDF
    # In real usage, you'd point to an actual PDF file

    import tempfile
    import fitz  # PyMuPDF

    # Create a test PDF
    pdf_path = tempfile.mktemp(suffix=".pdf")

    try:
        doc = fitz.open()
        page = doc.new_page()
        text = """
        Test Document Title

        Author: Test Author

        Abstract:
        This is a test document created for verifying PDF extraction functionality.
        The Alexandria research library should be able to extract this text correctly.

        Introduction:
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
        tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
        quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo.

        Methods:
        We implemented a comprehensive extraction pipeline that handles multiple
        document types including PDFs, web articles, and academic papers from arXiv.

        Results:
        The system successfully extracts text, metadata, and structural information
        from various document formats with high accuracy.

        Conclusion:
        This test demonstrates the PDF extraction capabilities of the Alexandria
        research library system.
        """
        page.insert_text((72, 72), text, fontsize=11)
        doc.save(pdf_path)
        doc.close()

        # Now test extraction
        content = await extract_content(file_path=pdf_path)

        print(f"\nSource Type: {content.source_type}")
        print(f"Title: {content.title}")
        print(f"Authors: {content.authors}")
        print(f"Page Count: {content.metadata.get('page_count')}")
        print(f"Text Length: {len(content.text)} characters")
        print(f"Text Preview: {content.text[:500]}...")

        # Assertions
        assert content.source_type == "pdf"
        assert content.text is not None and len(content.text) > 100
        assert "extraction" in content.text.lower() or "alexandria" in content.text.lower()

        print("\n[PASS] PDF extraction successful!")
        return True

    except Exception as e:
        print(f"\n[FAIL] PDF extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up test PDF
        Path(pdf_path).unlink(missing_ok=True)


async def test_extractor_detection():
    """Test that the correct extractor is selected for different URLs"""
    print("\n" + "=" * 60)
    print("TEST 4: Extractor Detection")
    print("=" * 60)

    test_cases = [
        ("https://arxiv.org/abs/2301.07041", ArxivExtractor, "ArXiv URL"),
        ("https://arxiv.org/pdf/2301.07041.pdf", ArxivExtractor, "ArXiv PDF URL"),
        ("https://example.com/article.html", URLExtractor, "Generic URL"),
        ("https://paulgraham.com/startupideas.html", URLExtractor, "Blog URL"),
    ]

    all_passed = True

    for url, expected_extractor, description in test_cases:
        detected = None
        for extractor_class in [ArxivExtractor, URLExtractor]:
            if extractor_class.can_handle(url):
                detected = extractor_class
                break

        status = "[PASS]" if detected == expected_extractor else "[FAIL]"
        if detected != expected_extractor:
            all_passed = False

        print(f"{status} {description}: {url}")
        print(f"       Expected: {expected_extractor.__name__}, Got: {detected.__name__ if detected else 'None'}")

    return all_passed


async def run_all_tests():
    """Run all extraction tests"""
    print("\n" + "#" * 60)
    print("# Alexandria Extractor Tests")
    print("#" * 60)

    results = {
        "URL Extraction": await test_url_extraction(),
        "ArXiv Extraction": await test_arxiv_extraction(),
        "PDF Extraction": await test_pdf_extraction(),
        "Extractor Detection": await test_extractor_detection(),
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
