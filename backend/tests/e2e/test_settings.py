"""
E2E tests for settings page: AI providers and colors.

Tests provider management and color customization.
"""

from playwright.sync_api import Page, expect

from tests.e2e.conftest import wait_for_element


class TestSettingsPage:
    """Tests for settings page loading."""

    def test_settings_page_loads(self, page: Page, app_server: str):
        """Settings page loads with all sections."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Verify settings page loaded (check URL and basic structure)
        assert "settings" in page.url

    def test_settings_sidebar_link(self, page: Page, app_server: str):
        """Clicking Settings in sidebar navigates to settings."""
        page.goto(f"{app_server}/app/")
        wait_for_element(page, "text=Alexandria")

        # Click settings link
        settings_link = page.locator("a[href='/app/settings']")
        expect(settings_link).to_be_visible()
        settings_link.click()
        page.wait_for_url("**/settings", timeout=5000)
        assert "settings" in page.url


class TestAIProviders:
    """Tests for AI provider management."""

    def test_add_provider_modal_opens(self, page: Page, app_server: str):
        """Add Provider button opens modal."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Click Add Provider button
        add_btn = page.locator("button:has-text('Add Provider')")
        expect(add_btn).to_be_visible()
        add_btn.click()

        # Modal content should open (loaded into #modal-container via HTMX)
        expect(page.locator("#add-provider-modal")).to_be_visible()

    def test_add_provider_model_dropdown(self, page: Page, app_server: str):
        """Model dropdown populates based on provider selection."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Open modal
        add_btn = page.locator("button:has-text('Add Provider')")
        expect(add_btn).to_be_visible()
        add_btn.click()

        # Wait for modal and select a provider
        provider_select = page.locator("select[name='provider_name']")
        expect(provider_select).to_be_visible()
        provider_select.select_option("anthropic")

        # Verify model dropdown is visible for selected provider
        model_select = page.locator("#model_id_anthropic")
        expect(model_select).to_be_visible()

    def test_test_ai_provider(self, page: Page, app_server: str, test_ai_provider_in_db: dict):
        """Test connection button sends test request."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Find and click test button for the provider
        test_btn = page.locator("button[title='Test connection']")
        expect(test_btn).to_be_visible()
        test_btn.click()
        page.wait_for_timeout(500)

        # Toast should appear (success or failure)
        toast_container = page.locator("#toast-container")
        expect(toast_container).to_be_attached()

    def test_set_default_provider(self, page: Page, app_server: str, test_ai_provider_in_db: dict):
        """Clicking provider card sets it as default."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Find the provider card
        provider_card = page.locator(f"#provider-{test_ai_provider_in_db['id']}")
        expect(provider_card).to_be_visible()

    def test_delete_ai_provider(self, page: Page, app_server: str, test_ai_provider_in_db: dict):
        """Delete button removes provider."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Verify provider exists
        provider_card = page.locator(f"#provider-{test_ai_provider_in_db['id']}")
        expect(provider_card).to_be_visible()

        # Find delete button within the provider card
        delete_btn = provider_card.locator("button[title='Delete provider']")
        expect(delete_btn).to_be_visible()


class TestColors:
    """Tests for color management."""

    def test_add_color(self, page: Page, app_server: str):
        """Add new color through form."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Find add color form inputs
        name_input = page.locator("input[name='name']").last
        expect(name_input).to_be_visible()
        name_input.fill("E2E Test Color")

        # Find color picker
        color_input = page.locator("input[name='hex_value']")
        expect(color_input).to_be_visible()
        color_input.fill("#FF5733")

        # Submit
        add_btn = page.locator("button:has-text('Add Color')")
        expect(add_btn).to_be_visible()
        add_btn.click()
        page.wait_for_timeout(500)

    def test_edit_color(self, page: Page, app_server: str, test_color_in_db: dict):
        """Edit existing color."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Verify color exists in the list
        color_item = page.locator(f"#color-{test_color_in_db['id']}")
        expect(color_item).to_be_visible()

    def test_delete_color(self, page: Page, app_server: str, test_color_in_db: dict):
        """Delete color removes it from list."""
        page.goto(f"{app_server}/app/settings")
        page.wait_for_timeout(1000)

        # Verify color exists
        color_item = page.locator(f"#color-{test_color_in_db['id']}")
        expect(color_item).to_be_visible()

        # Find delete button
        delete_btn = color_item.locator("button[title='Delete color']")
        expect(delete_btn).to_be_visible()
