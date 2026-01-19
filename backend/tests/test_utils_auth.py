"""
Tests for authentication utilities (app/utils/auth.py).

Tests password hashing and the get_current_user dependency
that bootstraps default users, categories, and colors.
"""

import pytest
from sqlalchemy import select

from app.models.category import Category
from app.models.color import Color
from app.models.user import User
from app.utils.auth import (
    DEFAULT_CATEGORIES,
    DEFAULT_COLORS,
    get_current_user,
    hash_password,
    pwd_context,
)


# =============================================================================
# Password Hashing Tests
# =============================================================================


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a bcrypt hash."""
        password = "test_password_123"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$ (or $2a$, $2y$)
        assert hashed.startswith("$2")
        assert len(hashed) == 60  # Standard bcrypt hash length

    def test_hash_password_different_for_same_input(self):
        """Test that hashing same password produces different hashes (due to salt)."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Each hash should be unique due to random salt
        assert hash1 != hash2

    def test_hash_password_verifiable(self):
        """Test that hashed password can be verified."""
        password = "verify_me_123"
        hashed = hash_password(password)

        # Use passlib context to verify
        assert pwd_context.verify(password, hashed) is True
        assert pwd_context.verify("wrong_password", hashed) is False

    def test_hash_password_handles_unicode(self):
        """Test password hashing with unicode characters."""
        password = "пароль_密码_🔒"
        hashed = hash_password(password)

        assert pwd_context.verify(password, hashed) is True

    def test_hash_password_handles_empty_string(self):
        """Test password hashing with empty string."""
        password = ""
        hashed = hash_password(password)

        # Empty password should still produce valid hash
        assert hashed.startswith("$2")
        assert pwd_context.verify("", hashed) is True

    def test_hash_password_handles_long_password(self):
        """Test password hashing with very long password."""
        # bcrypt has a 72-byte limit, but should handle gracefully
        password = "a" * 100
        hashed = hash_password(password)

        assert hashed.startswith("$2")


# =============================================================================
# get_current_user() Tests
# =============================================================================


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_returns_existing_user(self, async_db_session, test_user):
        """Test that existing user is returned from session."""
        # The session already has test_user from the fixture
        result = await async_db_session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        assert user is not None
        # Verify we can query the user
        assert user.email is not None

    def test_get_current_user_is_dependency(self):
        """Test that get_current_user is a valid FastAPI dependency."""
        import inspect
        # get_current_user should be an async function
        assert inspect.iscoroutinefunction(get_current_user)


# =============================================================================
# Default Data Bootstrap Tests
# =============================================================================


class TestDefaultDataBootstrap:
    """Tests for default categories and colors."""

    def test_default_categories_structure(self):
        """Test DEFAULT_CATEGORIES has expected structure."""
        assert len(DEFAULT_CATEGORIES) > 0

        for cat in DEFAULT_CATEGORIES:
            assert "name" in cat
            assert "children" in cat
            assert isinstance(cat["children"], list)

    def test_default_categories_includes_ai(self):
        """Test AI & Machine Learning category exists."""
        category_names = [cat["name"] for cat in DEFAULT_CATEGORIES]
        assert "AI & Machine Learning" in category_names

    def test_ai_category_has_subcategories(self):
        """Test AI category has subcategories."""
        ai_cat = next(
            cat for cat in DEFAULT_CATEGORIES if cat["name"] == "AI & Machine Learning"
        )
        assert len(ai_cat["children"]) > 0
        assert "Safety" in ai_cat["children"]

    def test_default_colors_structure(self):
        """Test DEFAULT_COLORS has expected structure."""
        assert len(DEFAULT_COLORS) > 0

        for color in DEFAULT_COLORS:
            assert "name" in color
            assert "hex_value" in color
            # Validate hex color format
            assert color["hex_value"].startswith("#")
            assert len(color["hex_value"]) == 7

    def test_default_colors_includes_essential_colors(self):
        """Test essential status colors exist."""
        color_names = [c["name"] for c in DEFAULT_COLORS]
        assert "Unread" in color_names
        assert "Important" in color_names
        assert "Archived" in color_names

    def test_default_colors_hex_values_valid(self):
        """Test all hex values are valid colors."""
        import re

        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")

        for color in DEFAULT_COLORS:
            assert hex_pattern.match(color["hex_value"]), (
                f"Invalid hex: {color['hex_value']}"
            )


# =============================================================================
# Integration Tests
# =============================================================================


class TestAuthIntegration:
    """Integration tests for auth with database."""

    @pytest.mark.asyncio
    async def test_password_hash_stored_correctly(self, async_db_session):
        """Test that password hash is stored and retrievable."""
        password = "integration_test_password"
        hashed = hash_password(password)

        user = User(
            email="integration@test.com",
            password_hash=hashed,
        )
        async_db_session.add(user)
        await async_db_session.commit()
        await async_db_session.refresh(user)

        # Verify the stored hash works
        assert pwd_context.verify(password, user.password_hash) is True

        # Cleanup
        await async_db_session.delete(user)
        await async_db_session.commit()
