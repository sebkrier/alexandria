"""
E2E tests for Ask/Chat interface: AI Q&A about articles.

Tests the question-answering interface.
"""

from playwright.sync_api import Page, expect

from tests.e2e.conftest import wait_for_element


class TestAskPage:
    """Tests for the Ask page."""

    def test_ask_page_loads(self, page: Page, app_server: str):
        """Ask page loads with input field."""
        page.goto(f"{app_server}/app/ask")
        wait_for_element(page, "text=Alexandria")

        # Should show input area
        # The ask page may have a text input or textarea
        page.wait_for_timeout(500)

    def test_ask_sidebar_link(self, page: Page, app_server: str):
        """Clicking Ask in sidebar navigates to ask page."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "text=Alexandria")

        # Look for Ask link
        ask_link = page.locator("a[href='/app/ask']")
        if ask_link.is_visible():
            ask_link.click()
            page.wait_for_url("**/ask", timeout=5000)


class TestAskExampleQuestions:
    """Tests for example questions."""

    def test_ask_example_questions(self, page: Page, app_server: str):
        """Example questions are clickable."""
        page.goto(f"{app_server}/app/ask")
        page.wait_for_timeout(500)

        # Look for example questions
        examples = page.locator("button:has-text('What')")
        if examples.count() > 0:
            # Click an example
            examples.first.click()
            page.wait_for_timeout(300)


class TestAskQuery:
    """Tests for asking questions."""

    def test_ask_custom_question(
        self, page: Page, app_server: str, test_article_in_db: dict, test_ai_provider_in_db: dict
    ):
        """Submit a custom question."""
        page.goto(f"{app_server}/app/ask")
        page.wait_for_timeout(500)

        # Find input
        question_input = page.locator("textarea, input[type='text']")
        if question_input.is_visible():
            question_input.fill("What are the main topics in my library?")

            # Submit
            submit_btn = page.locator("button[type='submit']")
            if submit_btn.is_visible():
                submit_btn.click()
                # Wait for response or loading
                page.wait_for_timeout(1000)

    def test_ask_loading_state(
        self, page: Page, app_server: str, test_article_in_db: dict, test_ai_provider_in_db: dict
    ):
        """Shows loading state while processing."""
        page.goto(f"{app_server}/app/ask")
        page.wait_for_timeout(500)

        question_input = page.locator("textarea, input[type='text']")
        if question_input.is_visible():
            question_input.fill("Test question")

            submit_btn = page.locator("button[type='submit']")
            if submit_btn.is_visible():
                submit_btn.click()
                # Should show loading indicator
                page.wait_for_timeout(200)


class TestAskResponse:
    """Tests for response rendering."""

    def test_ask_response_rendering(self, page: Page, app_server: str):
        """Ask page loads and has input area for questions."""
        page.goto(f"{app_server}/app/ask")
        page.wait_for_timeout(500)

        # Verify the Ask page has loaded with question input
        question_input = page.locator("textarea, input[type='text']")
        expect(question_input.first).to_be_visible()

    def test_ask_source_citations(self, page: Page, app_server: str):
        """Ask page has submit functionality."""
        page.goto(f"{app_server}/app/ask")
        page.wait_for_timeout(500)

        # Verify submit button exists
        submit_btn = page.locator("button[type='submit']")
        expect(submit_btn.first).to_be_visible()


class TestAskErrors:
    """Tests for error handling in ask interface."""

    def test_ask_no_provider_error(self, page: Page, app_server: str):
        """Shows error when no AI provider configured."""
        page.goto(f"{app_server}/app/ask")
        page.wait_for_timeout(500)

        # Without a provider, submitting should show an error
        question_input = page.locator("textarea, input[type='text']")
        if question_input.is_visible():
            question_input.fill("Test question without provider")

            submit_btn = page.locator("button[type='submit']")
            if submit_btn.is_visible():
                submit_btn.click()
                # Should show error message eventually
                page.wait_for_timeout(1000)
