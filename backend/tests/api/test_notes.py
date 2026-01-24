"""
Tests for the notes API endpoints.

Coverage target: 90%+ of app/api/routes/notes.py
"""

from uuid import uuid4

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def test_note(async_db_session, test_article):
    """Create a test note attached to the test article."""
    from app.models.note import Note

    note = Note(
        article_id=test_article.id,
        content="This is a test note.",
    )
    async_db_session.add(note)
    await async_db_session.commit()
    await async_db_session.refresh(note)
    return note


class TestGetArticleNotes:
    """Tests for GET /api/articles/{article_id}/notes endpoint."""

    @pytest.mark.asyncio
    async def test_get_notes_empty(self, test_client, test_article):
        """Test getting notes when article has none."""
        response = await test_client.get(f"/api/articles/{test_article.id}/notes")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_notes_with_data(self, test_client, test_article, test_note):
        """Test getting notes returns existing notes."""
        response = await test_client.get(f"/api/articles/{test_article.id}/notes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == test_note.content
        assert data[0]["article_id"] == str(test_article.id)

    @pytest.mark.asyncio
    async def test_get_notes_article_not_found(self, test_client):
        """Test getting notes for non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.get(f"/api/articles/{fake_id}/notes")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_notes_wrong_user(self, test_client, async_db_session):
        """Test user cannot access another user's article notes."""
        from app.models.article import Article, ProcessingStatus, SourceType
        from app.models.user import User

        # Create another user and their article
        other_user = User(
            email=f"other-{uuid4()}@test.com",
            password_hash="fakehash",
        )
        async_db_session.add(other_user)
        await async_db_session.flush()

        other_article = Article(
            user_id=other_user.id,
            source_type=SourceType.URL,
            title="Other Article",
            extracted_text="content",
            processing_status=ProcessingStatus.COMPLETED,
        )
        async_db_session.add(other_article)
        await async_db_session.commit()

        response = await test_client.get(f"/api/articles/{other_article.id}/notes")

        assert response.status_code == 404


class TestCreateNote:
    """Tests for POST /api/articles/{article_id}/notes endpoint."""

    @pytest.mark.asyncio
    async def test_create_note_success(self, test_client, test_article):
        """Test creating a new note."""
        response = await test_client.post(
            f"/api/articles/{test_article.id}/notes",
            json={"content": "A new note with important information."},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "A new note with important information."
        assert data["article_id"] == str(test_article.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_note_article_not_found(self, test_client):
        """Test creating note for non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.post(
            f"/api/articles/{fake_id}/notes",
            json={"content": "Note content"},
        )

        assert response.status_code == 404


class TestUpdateNote:
    """Tests for PATCH /api/notes/{note_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_note_success(self, test_client, test_note):
        """Test updating an existing note."""
        response = await test_client.patch(
            f"/api/notes/{test_note.id}",
            json={"content": "Updated note content."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated note content."
        assert data["id"] == str(test_note.id)

    @pytest.mark.asyncio
    async def test_update_note_not_found(self, test_client):
        """Test updating non-existent note returns 404."""
        fake_id = uuid4()
        response = await test_client.patch(
            f"/api/notes/{fake_id}",
            json={"content": "New content"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_note_wrong_user(self, test_client, async_db_session):
        """Test user cannot update another user's note."""
        from app.models.article import Article, ProcessingStatus, SourceType
        from app.models.note import Note
        from app.models.user import User

        # Create another user, article, and note
        other_user = User(
            email=f"other-{uuid4()}@test.com",
            password_hash="fakehash",
        )
        async_db_session.add(other_user)
        await async_db_session.flush()

        other_article = Article(
            user_id=other_user.id,
            source_type=SourceType.URL,
            title="Other Article",
            extracted_text="content",
            processing_status=ProcessingStatus.COMPLETED,
        )
        async_db_session.add(other_article)
        await async_db_session.flush()

        other_note = Note(
            article_id=other_article.id,
            content="Other user's note",
        )
        async_db_session.add(other_note)
        await async_db_session.commit()

        response = await test_client.patch(
            f"/api/notes/{other_note.id}",
            json={"content": "Trying to update"},
        )

        assert response.status_code == 404


class TestDeleteNote:
    """Tests for DELETE /api/notes/{note_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_note_success(self, test_client, test_article, test_note):
        """Test deleting an existing note."""
        response = await test_client.delete(f"/api/notes/{test_note.id}")

        assert response.status_code == 204

        # Verify note is deleted
        list_response = await test_client.get(f"/api/articles/{test_article.id}/notes")
        assert list_response.json() == []

    @pytest.mark.asyncio
    async def test_delete_note_not_found(self, test_client):
        """Test deleting non-existent note returns 404."""
        fake_id = uuid4()
        response = await test_client.delete(f"/api/notes/{fake_id}")

        assert response.status_code == 404
