"""
E2E Test Fixtures for Alexandria.

Provides browser automation via Playwright and a running uvicorn server
for testing the full HTMX + Alpine.js frontend.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import closing
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

# Test database configuration
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria_test",
)

# Track server state for health checks
_server_process = None
_server_base_url = None
_test_count = 0
_max_tests_before_restart = 4  # Restart server every N tests to prevent resource exhaustion


def find_free_port() -> int:
    """Find a free port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """Wait for server to be ready by polling the health endpoint."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(f"{url}/", timeout=1.0)
            if response.status_code == 200:
                return True
        except httpx.RequestError:
            pass
        time.sleep(0.2)
    return False


def check_server_health(url: str, timeout: float = 2.0) -> bool:
    """Quick health check to verify server is still responsive."""
    try:
        response = httpx.get(f"{url}/", timeout=timeout)
        return response.status_code == 200
    except httpx.RequestError:
        return False


def restart_server_if_needed(force: bool = False) -> bool:
    """Restart the server if it's unresponsive or force is True."""
    global _server_process, _server_base_url

    should_restart = force or (_server_base_url and not check_server_health(_server_base_url))

    if should_restart:
        # Kill existing server
        if _server_process:
            _server_process.terminate()
            try:
                _server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _server_process.kill()
                _server_process.wait(timeout=2)
            _server_process = None

        # Longer delay to ensure port is released and system resources freed
        time.sleep(1.0)

        # Start new server on a NEW port (avoids port reuse issues)
        new_port = find_free_port()
        new_base_url = f"http://127.0.0.1:{new_port}"

        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL

        _server_process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(new_port),
            ],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not wait_for_server(new_base_url, timeout=30.0):
            raise RuntimeError("Failed to restart server")

        _server_base_url = new_base_url
        return True
    return False


def get_server_url() -> str:
    """Get the current server URL (may change after restarts)."""
    return _server_base_url


@pytest.fixture(scope="session")
def _start_initial_server() -> Generator[None, None, None]:
    """
    Start the initial uvicorn server for E2E tests.

    This is an internal fixture that starts the server once per session.
    The actual URL should be accessed via get_server_url() since it may change.
    """
    global _server_process, _server_base_url

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    # Set test database URL for the server process
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL

    # Start uvicorn server
    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to be ready
    if not wait_for_server(base_url, timeout=30.0):
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        raise RuntimeError(
            f"Server failed to start.\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        )

    # Store globally for health checks and restarts
    _server_process = process
    _server_base_url = base_url

    yield

    # Cleanup
    if _server_process:
        _server_process.terminate()
        try:
            _server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _server_process.kill()


@pytest.fixture(scope="function")
def app_server(_start_initial_server) -> Generator[str, None, None]:
    """
    Get the server URL for a test.

    This fixture ensures the server is healthy and restarts it if needed.
    The URL may be different between tests if the server was restarted.
    """
    global _test_count

    _test_count += 1

    # Force restart every N tests to prevent resource exhaustion
    if _test_count > 1 and _test_count % _max_tests_before_restart == 0:
        restart_server_if_needed(force=True)
    elif not check_server_health(_server_base_url, timeout=3.0):
        # Server is unhealthy, restart it
        restart_server_if_needed(force=True)

    yield _server_base_url


@pytest.fixture(scope="session")
def browser() -> Generator[Browser, None, None]:
    """Playwright browser instance (session-scoped for performance)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not os.environ.get("HEADED"))
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Browser context per test (isolated cookies, storage)."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Browser page per test."""
    page = context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function")
def test_user_id() -> str:
    """Generate a unique test user ID."""
    return str(uuid4())


@pytest.fixture(scope="function")
def mock_extraction():
    """
    Mock content extraction to avoid external HTTP calls.

    Returns consistent test content for fast, reliable tests.
    """
    from app.extractors.base import ExtractedContent

    async def mock_extract(url: str = None, file_path: str = None) -> ExtractedContent:
        return ExtractedContent(
            title="E2E Test Article: Understanding Transformers",
            text=(
                "The Transformer architecture has revolutionized natural language processing. "
                "Introduced in 2017, it uses self-attention mechanisms to process sequences "
                "in parallel rather than sequentially. This enables much faster training "
                "and has led to models like BERT, GPT, and their successors. "
                "Key contributions include multi-head attention and positional encoding. "
            )
            * 10,  # Repeat for realistic length
            authors=["Test Author"],
            source_type="url",
            original_url=url or "https://example.com/test-article",
        )

    with patch("app.extractors.extract_content", mock_extract):
        with patch("app.extractors.url.URLExtractor.extract", mock_extract):
            yield mock_extract


@pytest.fixture(scope="function")
def mock_ai_service():
    """
    Mock AI service to avoid LLM API calls.

    Makes processing instant and free.
    """
    mock_service = AsyncMock()

    # Mock process_article to do nothing (article stays in PENDING)
    mock_service.process_article = AsyncMock(return_value=None)

    with patch("app.ai.service.AIService", return_value=mock_service):
        yield mock_service


@pytest.fixture(scope="function")
def mock_embeddings():
    """Mock embedding generation to avoid loading the model."""
    import numpy as np

    async def mock_generate(text: str):
        # Return a random-ish but deterministic embedding
        return list(np.random.RandomState(42).rand(768).astype(float))

    with patch("app.ai.embeddings.generate_embedding", mock_generate):
        yield mock_generate


@pytest.fixture(scope="function")
def mock_external_services(mock_extraction, mock_ai_service, mock_embeddings):
    """Convenience fixture that mocks all external services."""
    return {
        "extraction": mock_extraction,
        "ai_service": mock_ai_service,
        "embeddings": mock_embeddings,
    }


# =============================================================================
# Database fixtures for E2E tests
# =============================================================================


def run_async(coro):
    """Run an async function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(scope="function")
def test_article_in_db(app_server):
    """
    Create a test article directly in the database.

    Returns the article ID.
    """
    import psycopg

    # Parse connection string
    db_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get the default user (created by auth.py)
            cur.execute("SELECT id FROM users LIMIT 1")
            row = cur.fetchone()
            if not row:
                # Create a test user
                user_id = uuid4()
                cur.execute(
                    "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                    (user_id, "e2e-test@alexandria.local", "fakehash"),
                )
            else:
                user_id = row[0]

            # Create a test article
            article_id = uuid4()
            cur.execute(
                """
                INSERT INTO articles (
                    id, user_id, source_type, original_url, title,
                    extracted_text, word_count, processing_status, is_read, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    article_id,
                    user_id,
                    "url",
                    "https://example.com/e2e-test-article",
                    "E2E Test Article",
                    "This is test content for E2E testing. " * 20,
                    100,
                    "completed",
                    False,
                ),
            )
            conn.commit()

            yield {"id": str(article_id), "user_id": str(user_id)}

            # Cleanup
            cur.execute("DELETE FROM articles WHERE id = %s", (article_id,))
            conn.commit()


@pytest.fixture(scope="function")
def multiple_test_articles(app_server):
    """
    Create multiple test articles for bulk operation tests.

    Returns list of article data dicts.
    """
    import psycopg

    db_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    articles = []

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get or create user
            cur.execute("SELECT id FROM users LIMIT 1")
            row = cur.fetchone()
            if not row:
                user_id = uuid4()
                cur.execute(
                    "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                    (user_id, "e2e-test@alexandria.local", "fakehash"),
                )
            else:
                user_id = row[0]

            # Create 5 test articles
            for i in range(5):
                article_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO articles (
                        id, user_id, source_type, original_url, title,
                        extracted_text, word_count, processing_status, is_read, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        article_id,
                        user_id,
                        "url",
                        f"https://example.com/e2e-article-{i}",
                        f"E2E Test Article {i + 1}",
                        f"Content for article {i + 1}. " * 20,
                        100,
                        "completed",
                        i % 2 == 0,  # Alternate read/unread
                    ),
                )
                articles.append({"id": str(article_id), "title": f"E2E Test Article {i + 1}"})

            conn.commit()
            yield {"articles": articles, "user_id": str(user_id)}

            # Cleanup
            for article in articles:
                cur.execute("DELETE FROM articles WHERE id = %s", (article["id"],))
            conn.commit()


@pytest.fixture(scope="function")
def test_category_in_db(app_server):
    """Create a test category in the database."""
    import psycopg

    db_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get user
            cur.execute("SELECT id FROM users LIMIT 1")
            row = cur.fetchone()
            if not row:
                user_id = uuid4()
                cur.execute(
                    "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                    (user_id, "e2e-test@alexandria.local", "fakehash"),
                )
            else:
                user_id = row[0]

            category_id = uuid4()
            cur.execute(
                "INSERT INTO categories (id, user_id, name, position) VALUES (%s, %s, %s, %s)",
                (category_id, user_id, "E2E Test Category", 0),
            )
            conn.commit()

            yield {"id": str(category_id), "name": "E2E Test Category"}

            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
            conn.commit()


@pytest.fixture(scope="function")
def test_color_in_db(app_server):
    """Create a test color in the database."""
    import psycopg

    db_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get user
            cur.execute("SELECT id FROM users LIMIT 1")
            row = cur.fetchone()
            if not row:
                user_id = uuid4()
                cur.execute(
                    "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                    (user_id, "e2e-test@alexandria.local", "fakehash"),
                )
            else:
                user_id = row[0]

            color_id = uuid4()
            cur.execute(
                "INSERT INTO colors (id, user_id, name, hex_value, position) VALUES (%s, %s, %s, %s, %s)",
                (color_id, user_id, "E2E Test Color", "#FF5733", 99),
            )
            conn.commit()

            yield {"id": str(color_id), "name": "E2E Test Color", "hex_value": "#FF5733"}

            cur.execute("DELETE FROM colors WHERE id = %s", (color_id,))
            conn.commit()


@pytest.fixture(scope="function")
def test_ai_provider_in_db(app_server):
    """Create a test AI provider in the database."""
    import psycopg

    db_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get user
            cur.execute("SELECT id FROM users LIMIT 1")
            row = cur.fetchone()
            if not row:
                user_id = uuid4()
                cur.execute(
                    "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                    (user_id, "e2e-test@alexandria.local", "fakehash"),
                )
            else:
                user_id = row[0]

            provider_id = uuid4()
            # Use a simple encrypted key for testing
            cur.execute(
                """
                INSERT INTO ai_providers (
                    id, user_id, provider_name, display_name, model_id,
                    api_key_encrypted, is_default, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    provider_id,
                    user_id,
                    "anthropic",
                    "E2E Test Claude",
                    "claude-sonnet-4-20250514",
                    "gAAAAABtest-encrypted-key",  # Fake encrypted key
                    True,
                    True,
                ),
            )
            conn.commit()

            yield {"id": str(provider_id), "display_name": "E2E Test Claude"}

            cur.execute("DELETE FROM ai_providers WHERE id = %s", (provider_id,))
            conn.commit()


# =============================================================================
# Helper functions for tests
# =============================================================================


def wait_for_htmx(page: Page, timeout: int = 5000):
    """Wait for HTMX to finish all pending requests."""
    page.wait_for_function(
        "() => !document.body.classList.contains('htmx-request')",
        timeout=timeout,
    )


def wait_for_element(page: Page, selector: str, timeout: int = 5000):
    """Wait for an element to appear in the DOM."""
    page.wait_for_selector(selector, timeout=timeout)


def click_and_wait(page: Page, selector: str, timeout: int = 5000):
    """Click an element and wait for HTMX to complete."""
    page.click(selector)
    wait_for_htmx(page, timeout)
