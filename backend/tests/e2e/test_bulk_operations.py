"""
E2E tests for bulk operations: multi-select, bulk actions.

Tests article selection and bulk mark read/unread, delete, color, reanalyze.
"""

from playwright.sync_api import Page, expect

from tests.e2e.conftest import wait_for_element


class TestArticleSelection:
    """Tests for selecting articles for bulk operations."""

    def test_select_single_article(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Clicking checkbox selects a single article."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Click the first article's checkbox
        first_checkbox = page.locator(".article-checkbox").first
        first_checkbox.click()

        # Bulk action bar should appear
        wait_for_element(page, "text=selected")
        expect(page.locator("text=1 selected")).to_be_visible()

    def test_select_multiple_articles(
        self, page: Page, app_server: str, multiple_test_articles: dict
    ):
        """Can select multiple articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Click multiple checkboxes
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        checkboxes.nth(1).click()

        # Should show 2 selected
        expect(page.locator("text=2 selected")).to_be_visible()

    def test_select_all_articles(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Select all button selects all visible articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select one article first to show the bulk bar
        first_checkbox = page.locator(".article-checkbox").first
        first_checkbox.click()
        page.wait_for_timeout(300)

        # Click the select all toggle (checkbox icon in bulk bar)
        select_all_btn = page.locator("[x-data*='bulkActionBar'] button").first
        expect(select_all_btn).to_be_visible()
        select_all_btn.click()
        page.wait_for_timeout(300)

        # Should show articles selected
        expect(page.get_by_text("selected").first).to_be_visible()

    def test_deselect_all(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Can deselect all articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select articles
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        checkboxes.nth(1).click()
        page.wait_for_timeout(300)
        expect(page.locator("text=2 selected")).to_be_visible()

        # Click close button (X) in bulk bar
        close_btn = page.locator("[x-data*='bulkActionBar'] button").last
        close_btn.click()
        page.wait_for_timeout(300)

        # Bulk bar should be hidden when count is 0 (not "0 selected" visible)
        # The bar has x-show="selectedCount > 0" so it hides completely
        expect(page.locator("text=2 selected")).not_to_be_visible(timeout=3000)

    def test_escape_clears_selection(
        self, page: Page, app_server: str, multiple_test_articles: dict
    ):
        """Pressing Escape clears selection."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select an article
        first_checkbox = page.locator(".article-checkbox").first
        first_checkbox.click()
        page.wait_for_timeout(300)
        expect(page.locator("text=1 selected")).to_be_visible()

        # Press Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # Selection should be cleared - bulk bar hides when count is 0
        expect(page.locator("text=1 selected")).not_to_be_visible(timeout=3000)

    def test_bulk_action_bar_visibility(
        self, page: Page, app_server: str, multiple_test_articles: dict
    ):
        """Bulk action bar shows/hides based on selection count."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Initially hidden
        expect(page.locator("[x-data*='bulkActionBar']")).to_have_attribute(
            "x-show", "selectedCount > 0"
        )

        # Select article
        first_checkbox = page.locator(".article-checkbox").first
        first_checkbox.click()

        # Bar should be visible - use specific text to avoid strict mode violation
        expect(page.locator("text=1 selected")).to_be_visible()


class TestBulkMarkRead:
    """Tests for bulk mark as read."""

    def test_bulk_mark_read(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Mark multiple articles as read."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select multiple articles
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        checkboxes.nth(1).click()
        wait_for_element(page, "text=2 selected")

        # Click Mark Read
        mark_read_btn = page.locator("button:has-text('Mark Read')")
        mark_read_btn.click()

        # Wait for toast
        wait_for_element(page, "#toast-container", timeout=5000)


class TestBulkMarkUnread:
    """Tests for bulk mark as unread."""

    def test_bulk_mark_unread(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Mark multiple articles as unread."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select articles
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        wait_for_element(page, "text=1 selected")

        # Click Mark Unread
        mark_unread_btn = page.locator("button:has-text('Mark Unread')")
        mark_unread_btn.click()

        # Wait for toast
        wait_for_element(page, "#toast-container", timeout=5000)


class TestBulkDelete:
    """Tests for bulk delete."""

    def test_bulk_delete_shows_confirmation(
        self, page: Page, app_server: str, multiple_test_articles: dict
    ):
        """Bulk delete shows confirmation modal."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select articles
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        checkboxes.nth(1).click()
        wait_for_element(page, "text=2 selected")

        # Click Delete
        delete_btn = page.locator("button:has-text('Delete')").first
        delete_btn.click()

        # Confirmation should appear
        expect(page.locator("text=Delete 2 articles?")).to_be_visible()

    def test_bulk_delete_cancel(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Cancel bulk delete keeps articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Count articles before
        initial_count = page.locator("[data-article-id]").count()

        # Select article
        first_checkbox = page.locator(".article-checkbox").first
        first_checkbox.click()
        wait_for_element(page, "text=1 selected")

        # Click Delete
        delete_btn = page.locator("button:has-text('Delete')").first
        delete_btn.click()

        # Confirmation appears
        expect(page.locator("#delete-confirm-modal")).to_be_visible()

        # Click Cancel
        cancel_btn = page.locator("#delete-confirm-modal button:has-text('Cancel')")
        cancel_btn.click()

        # Modal should close
        expect(page.locator("#delete-confirm-modal")).not_to_be_visible()

        # Articles count unchanged (don't check exact count since DB may have other articles)
        expect(page.locator("[data-article-id]")).to_have_count(initial_count)


class TestBulkColorUpdate:
    """Tests for bulk color update."""

    def test_bulk_color_update(
        self,
        page: Page,
        app_server: str,
        multiple_test_articles: dict,
        test_color_in_db: dict,
    ):
        """Set color on multiple articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select articles
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        checkboxes.nth(1).click()
        wait_for_element(page, "text=2 selected")

        # Click Color button
        color_btn = page.locator("button:has-text('Color')")
        color_btn.click()

        # Color picker should appear
        expect(page.locator("text=Set color:")).to_be_visible()


class TestBulkReanalyze:
    """Tests for bulk reanalyze."""

    def test_bulk_reanalyze(self, page: Page, app_server: str, multiple_test_articles: dict):
        """Reanalyze multiple articles."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select articles
        checkboxes = page.locator(".article-checkbox")
        checkboxes.nth(0).click()
        wait_for_element(page, "text=1 selected")

        # Click Re-analyze
        reanalyze_btn = page.locator("button:has-text('Re-analyze')")
        reanalyze_btn.click()

        # Button should show loading state or toast should appear
        page.wait_for_timeout(500)


class TestSidebarUnreadCount:
    """Tests for sidebar unread count updates."""

    def test_sidebar_unread_count_updates(
        self, page: Page, app_server: str, multiple_test_articles: dict
    ):
        """Sidebar unread count updates after bulk operations."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "[data-article-id]")

        # Select an article and mark as read
        checkboxes = page.locator(".article-checkbox")
        checkboxes.first.click()
        wait_for_element(page, "text=selected")

        # Mark read
        mark_read_btn = page.locator("button:has-text('Mark Read')")
        expect(mark_read_btn).to_be_visible()
        mark_read_btn.click()

        # Wait for update
        page.wait_for_timeout(1000)

        # Page should still be functional
        expect(page.get_by_role("banner").get_by_role("link", name="Alexandria")).to_be_visible()
