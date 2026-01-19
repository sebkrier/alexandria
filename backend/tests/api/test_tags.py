"""
Tests for the tags API endpoints.

Coverage target: 90%+ of app/api/routes/tags.py
"""

from uuid import uuid4

import pytest


class TestListTags:
    """Tests for GET /api/tags endpoint."""

    @pytest.mark.asyncio
    async def test_list_tags_empty(self, test_client):
        """Test listing tags when none exist."""
        response = await test_client.get("/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_list_tags_with_data(self, test_client, test_tag):
        """Test listing tags returns existing tags."""
        response = await test_client.get("/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_tag.name
        assert data[0]["color"] == test_tag.color
        assert data[0]["article_count"] == 0

    @pytest.mark.asyncio
    async def test_list_tags_with_article_count(
        self, test_client, test_tag, test_article, async_db_session
    ):
        """Test tag article_count is calculated correctly."""
        from app.models.article_tag import ArticleTag

        # Associate tag with article
        article_tag = ArticleTag(article_id=test_article.id, tag_id=test_tag.id)
        async_db_session.add(article_tag)
        await async_db_session.commit()

        response = await test_client.get("/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["article_count"] == 1


class TestCreateTag:
    """Tests for POST /api/tags endpoint."""

    @pytest.mark.asyncio
    async def test_create_tag_success(self, test_client):
        """Test creating a new tag."""
        response = await test_client.post(
            "/api/tags",
            json={"name": "new-tag", "color": "#00FF00"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new-tag"
        assert data["color"] == "#00FF00"
        assert data["article_count"] == 0
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_tag_without_color(self, test_client):
        """Test creating a tag without specifying color."""
        response = await test_client.post(
            "/api/tags",
            json={"name": "colorless-tag"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "colorless-tag"
        assert data["color"] is None

    @pytest.mark.asyncio
    async def test_create_tag_duplicate(self, test_client, test_tag):
        """Test creating a tag with duplicate name fails."""
        response = await test_client.post(
            "/api/tags",
            json={"name": test_tag.name},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestDeleteTag:
    """Tests for DELETE /api/tags/{tag_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_tag_success(self, test_client, test_tag):
        """Test deleting an existing tag."""
        response = await test_client.delete(f"/api/tags/{test_tag.id}")

        assert response.status_code == 204

        # Verify tag is deleted
        list_response = await test_client.get("/api/tags")
        assert list_response.json() == []

    @pytest.mark.asyncio
    async def test_delete_tag_not_found(self, test_client):
        """Test deleting a non-existent tag returns 404."""
        fake_id = uuid4()
        response = await test_client.delete(f"/api/tags/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_tag_wrong_user(
        self, test_client, async_db_session
    ):
        """Test user cannot delete another user's tag."""
        from app.models.tag import Tag
        from app.models.user import User

        # Create another user and their tag
        other_user = User(
            email=f"other-{uuid4()}@test.com",
            password_hash="fakehash",
        )
        async_db_session.add(other_user)
        await async_db_session.flush()

        other_tag = Tag(
            user_id=other_user.id,
            name="other-tag",
        )
        async_db_session.add(other_tag)
        await async_db_session.commit()

        # Try to delete the other user's tag
        response = await test_client.delete(f"/api/tags/{other_tag.id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
