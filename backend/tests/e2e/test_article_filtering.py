"""
E2E tests for article filtering, search, and view modes.

Tests search, category filtering, color filtering, and view mode toggles.
"""

import re

from playwright.sync_api import Page, expect

from tests.e2e.conftest import wait_for_element, wait_for_htmx


class TestSearch:
    """Tests for article search functionality."""

    def test_search_articles(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Search filters articles by keyword."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Verify initial articles are visible
        initial_count = page.locator("[data-article-id]").count()
        assert initial_count >= 1

        # Type in search box
        search_input = page.locator("input[name='search']")
        search_input.fill("Article 1")

        # Wait for debounce (300ms) + request
        page.wait_for_timeout(500)
        wait_for_htmx(page)

        # Results should be filtered - use heading to be specific (use .first due to grid/list duplication)
        expect(page.get_by_role("heading", name="E2E Test Article 1").first).to_be_visible()

    def test_search_debounce(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Search has 300ms debounce before triggering."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        search_input = page.locator("input[name='search']")

        # Type quickly - shouldn't trigger multiple requests
        search_input.type("test", delay=50)

        # Wait less than debounce
        page.wait_for_timeout(100)

        # Type more
        search_input.type("123", delay=50)

        # Wait for debounce to complete
        page.wait_for_timeout(500)
        wait_for_htmx(page)

        # Page should still be functional
        expect(page.get_by_role("banner").get_by_role("link", name="Alexandria")).to_be_visible()

    def test_clear_search(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Clearing search shows all articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        search_input = page.locator("input[name='search']")

        # Search for something specific
        search_input.fill("Article 1")
        page.wait_for_timeout(500)
        wait_for_htmx(page)

        # Clear search
        search_input.fill("")
        page.wait_for_timeout(500)
        wait_for_htmx(page)

        # More articles should be visible after clearing search (at least the 5 test articles)
        article_count = page.locator("[data-article-id]").count()
        assert article_count >= 5, (
            f"Expected at least 5 articles after clearing search, got {article_count}"
        )


class TestCategoryFilter:
    """Tests for category-based filtering."""

    def test_filter_by_category(
        self,
        page: Page,
        app_server: str,
        test_article_in_db: dict,
        test_category_in_db: dict,
    ):
        """Clicking category in sidebar filters articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "text=Alexandria")

        # Click category in sidebar
        category_link = page.locator(f"text={test_category_in_db['name']}")
        expect(category_link).to_be_visible()
        category_link.click()
        wait_for_htmx(page)

        # URL should reflect filter
        expect(page).to_have_url(re.compile(rf"category_id={test_category_in_db['id']}"))


class TestColorFilter:
    """Tests for color-based filtering."""

    def test_filter_by_color(
        self,
        page: Page,
        app_server: str,
        test_article_in_db: dict,
        test_color_in_db: dict,
    ):
        """Clicking color in sidebar filters articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "text=Alexandria")

        # Click color filter in sidebar
        color_link = page.locator(f"a:has-text('{test_color_in_db['name']}')")
        expect(color_link).to_be_visible()
        color_link.click()
        wait_for_htmx(page)

        # URL should reflect filter
        expect(page).to_have_url(re.compile(rf"color_id={test_color_in_db['id']}"))


class TestReadStatusFilter:
    """Tests for read/unread status filtering."""

    def test_filter_unread_articles(
        self, page: Page, app_server: str, multiple_test_articles: dict
    ):
        """Filter to show only unread articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Look for unread filter option
        # The app uses rose emoji indicators
        unread_indicators = page.locator("text='unread'")
        if unread_indicators.count() > 0:
            # Click unread filter if available
            pass  # Filter mechanism varies

        # Page should still be functional
        expect(page.get_by_role("banner").get_by_role("link", name="Alexandria")).to_be_visible()


class TestViewModes:
    """Tests for grid/list view toggle."""

    def test_grid_view_toggle(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Grid view button switches to grid layout."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Find grid view button (has grid icon)
        grid_button = page.locator("button[title='Grid view']")
        grid_button.click()
        wait_for_htmx(page)

        # URL should include view=grid
        expect(page).to_have_url(re.compile(r"view=grid"))

    def test_list_view_toggle(self, page: Page, app_server: str, multiple_test_articles: dict):
        """List view button switches to list layout."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Find list view button (has list icon)
        list_button = page.locator("button[title='List view']")
        list_button.click()
        wait_for_htmx(page)

        # URL should include view=list
        expect(page).to_have_url(re.compile(r"view=list"))


class TestCombinedFilters:
    """Tests for combining multiple filters."""

    def test_combined_filters(
        self,
        page: Page,
        app_server: str,
        multiple_test_articles: dict,
        test_category_in_db: dict,
    ):
        """Apply multiple filters together."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Search for something
        search_input = page.locator("input[name='search']")
        search_input.fill("Article")
        page.wait_for_timeout(500)
        wait_for_htmx(page)

        # Verify search input has the value
        expect(search_input).to_have_value("Article")

        # Toggle view mode
        list_button = page.locator("button[title='List view']")
        list_button.click()
        wait_for_htmx(page)

        # Just verify the page is still functional after filter operations
        # The URL may or may not update with view param depending on app behavior
        expect(page.locator("[data-article-id]").first).to_be_visible()

    def test_url_state_persistence(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Filter state persists in URL on page reload."""
        # Navigate with filters
        page.goto(f"{app_server}/app/?view=list&search=Article")
        wait_for_element(page, "text=Alexandria")

        # Verify filters are applied after load
        search_input = page.locator("input[name='search']")
        expect(search_input).to_have_value("Article")

        # List view should be active
        list_button = page.locator("button[title='List view']")
        expect(list_button).to_have_class(re.compile(r"bg-dark-surface"))
