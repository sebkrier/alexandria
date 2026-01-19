"""
Tests for the categories API endpoints.

Coverage target: 85%+ of app/api/routes/categories.py
"""

from uuid import uuid4

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def test_child_category(async_db_session, test_user, test_category):
    """Create a child category under test_category."""
    from app.models.category import Category

    child = Category(
        user_id=test_user.id,
        name="Child Category",
        parent_id=test_category.id,
        position=0,
    )
    async_db_session.add(child)
    await async_db_session.commit()
    await async_db_session.refresh(child)
    return child


class TestListCategories:
    """Tests for GET /api/categories endpoint."""

    @pytest.mark.asyncio
    async def test_list_categories_empty(self, test_client):
        """Test listing categories when none exist."""
        response = await test_client.get("/api/categories")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_categories_flat(self, test_client, test_category):
        """Test listing a single root category."""
        response = await test_client.get("/api/categories")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_category.name
        assert data[0]["children"] == []
        assert data[0]["article_count"] == 0

    @pytest.mark.asyncio
    async def test_list_categories_nested(
        self, test_client, test_category, test_child_category
    ):
        """Test listing categories with parent-child relationship."""
        response = await test_client.get("/api/categories")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Only root category at top level

        parent = data[0]
        assert parent["name"] == test_category.name
        assert len(parent["children"]) == 1
        assert parent["children"][0]["name"] == test_child_category.name

    @pytest.mark.asyncio
    async def test_list_categories_with_article_count(
        self, test_client, test_category, test_article, async_db_session
    ):
        """Test category article_count is calculated correctly."""
        from app.models.article_category import ArticleCategory

        # Associate article with category
        article_category = ArticleCategory(
            article_id=test_article.id,
            category_id=test_category.id,
            is_primary=True,
        )
        async_db_session.add(article_category)
        await async_db_session.commit()

        response = await test_client.get("/api/categories")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["article_count"] == 1

    @pytest.mark.asyncio
    async def test_list_categories_cumulative_count(
        self,
        test_client,
        test_category,
        test_child_category,
        test_article,
        async_db_session,
    ):
        """Test parent category shows cumulative count from children."""
        from app.models.article_category import ArticleCategory

        # Associate article with child category
        article_category = ArticleCategory(
            article_id=test_article.id,
            category_id=test_child_category.id,
            is_primary=True,
        )
        async_db_session.add(article_category)
        await async_db_session.commit()

        response = await test_client.get("/api/categories")

        assert response.status_code == 200
        data = response.json()
        # Parent should show cumulative count (child's articles)
        assert data[0]["article_count"] == 1
        assert data[0]["children"][0]["article_count"] == 1


class TestCreateCategory:
    """Tests for POST /api/categories endpoint."""

    @pytest.mark.asyncio
    async def test_create_category_root(self, test_client):
        """Test creating a root category."""
        response = await test_client.post(
            "/api/categories",
            json={
                "name": "New Root Category",
                "description": "A description",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Root Category"
        assert data["description"] == "A description"
        assert data["parent_id"] is None
        assert data["article_count"] == 0
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_category_child(self, test_client, test_category):
        """Test creating a child category."""
        response = await test_client.post(
            "/api/categories",
            json={
                "name": "New Child",
                "parent_id": str(test_category.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Child"
        assert data["parent_id"] == str(test_category.id)

    @pytest.mark.asyncio
    async def test_create_category_position_auto_increment(
        self, test_client, test_category
    ):
        """Test category position auto-increments at same level."""
        # Create first sibling
        response1 = await test_client.post(
            "/api/categories",
            json={"name": "Sibling 1"},
        )
        pos1 = response1.json()["position"]

        # Create second sibling
        response2 = await test_client.post(
            "/api/categories",
            json={"name": "Sibling 2"},
        )
        pos2 = response2.json()["position"]

        assert pos2 > pos1


class TestUpdateCategory:
    """Tests for PATCH /api/categories/{category_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_category_name(self, test_client, test_category):
        """Test updating category name."""
        response = await test_client.patch(
            f"/api/categories/{test_category.id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_category_parent(
        self, test_client, test_category, async_db_session, test_user
    ):
        """Test moving category to a new parent."""
        from app.models.category import Category

        # Create another category to be the new parent
        new_parent = Category(
            user_id=test_user.id,
            name="New Parent",
            position=1,
        )
        async_db_session.add(new_parent)
        await async_db_session.commit()

        response = await test_client.patch(
            f"/api/categories/{test_category.id}",
            json={"parent_id": str(new_parent.id)},
        )

        assert response.status_code == 200
        assert response.json()["parent_id"] == str(new_parent.id)

    @pytest.mark.asyncio
    async def test_update_category_not_found(self, test_client):
        """Test updating non-existent category returns 404."""
        fake_id = uuid4()
        response = await test_client.patch(
            f"/api/categories/{fake_id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_category_description(self, test_client, test_category):
        """Test updating category description."""
        response = await test_client.patch(
            f"/api/categories/{test_category.id}",
            json={"description": "A new detailed description"},
        )

        assert response.status_code == 200
        assert response.json()["description"] == "A new detailed description"


class TestDeleteCategory:
    """Tests for DELETE /api/categories/{category_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_category_success(self, test_client, test_category):
        """Test deleting a category."""
        response = await test_client.delete(f"/api/categories/{test_category.id}")

        assert response.status_code == 204

        # Verify deleted
        list_response = await test_client.get("/api/categories")
        assert list_response.json() == []

    @pytest.mark.asyncio
    async def test_delete_category_not_found(self, test_client):
        """Test deleting non-existent category returns 404."""
        fake_id = uuid4()
        response = await test_client.delete(f"/api/categories/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_category_children_reparented(
        self, test_client, test_category, test_child_category
    ):
        """Test deleting parent category moves children to grandparent (or root)."""
        # Delete the parent
        response = await test_client.delete(f"/api/categories/{test_category.id}")
        assert response.status_code == 204

        # Check that child is now a root category
        list_response = await test_client.get("/api/categories")
        data = list_response.json()

        # Child should now be at root level
        assert len(data) == 1
        assert data[0]["name"] == test_child_category.name
        # It should have no children (it was a leaf)
        assert data[0]["children"] == []
