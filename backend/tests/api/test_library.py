"""
Tests for the library export/import API endpoints.

Coverage target: 80%+ of app/api/routes/library.py
"""

import json
from io import BytesIO

import pytest


def make_valid_backup(
    articles=None,
    categories=None,
    tags=None,
    version="1.0",
) -> dict:
    """Create a valid backup JSON structure."""
    return {
        "version": version,
        "exported_at": "2025-01-15T10:00:00",
        "categories": categories or [],
        "tags": tags or [],
        "articles": articles or [],
    }


class TestExportLibrary:
    """Tests for GET /api/library/export endpoint."""

    @pytest.mark.asyncio
    async def test_export_empty_library(self, test_client):
        """Test exporting an empty library."""
        response = await test_client.get("/api/library/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers.get("content-disposition", "")

        data = response.json()
        assert data["version"] == "1.0"
        assert data["categories"] == []
        assert data["tags"] == []
        assert data["articles"] == []

    @pytest.mark.asyncio
    async def test_export_with_articles(self, test_client, test_article):
        """Test exporting library with articles."""
        response = await test_client.get("/api/library/export")

        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["title"] == test_article.title
        assert data["articles"][0]["original_url"] == test_article.original_url

    @pytest.mark.asyncio
    async def test_export_with_categories(self, test_client, test_category):
        """Test exporting library with categories."""
        response = await test_client.get("/api/library/export")

        assert response.status_code == 200
        data = response.json()
        assert len(data["categories"]) == 1
        assert data["categories"][0]["name"] == test_category.name

    @pytest.mark.asyncio
    async def test_export_with_tags(self, test_client, test_tag):
        """Test exporting library with tags."""
        response = await test_client.get("/api/library/export")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) == 1
        assert data["tags"][0]["name"] == test_tag.name

    @pytest.mark.asyncio
    async def test_export_without_text(self, test_client, test_article):
        """Test exporting without extracted text."""
        response = await test_client.get("/api/library/export?include_text=false")

        assert response.status_code == 200
        data = response.json()
        assert data["articles"][0]["extracted_text"] is None

    @pytest.mark.asyncio
    async def test_export_with_text(self, test_client, test_article):
        """Test exporting with extracted text included."""
        response = await test_client.get("/api/library/export?include_text=true")

        assert response.status_code == 200
        data = response.json()
        assert data["articles"][0]["extracted_text"] is not None

    @pytest.mark.asyncio
    async def test_export_includes_notes(self, test_client, test_article, async_db_session):
        """Test exporting includes article notes."""
        from app.models.note import Note

        # Add a note to the article
        note = Note(article_id=test_article.id, content="Test note content")
        async_db_session.add(note)
        await async_db_session.commit()

        response = await test_client.get("/api/library/export")

        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"][0]["notes"]) == 1
        assert data["articles"][0]["notes"][0]["content"] == "Test note content"


class TestImportLibrary:
    """Tests for POST /api/library/import endpoint."""

    @pytest.mark.asyncio
    async def test_import_empty_backup(self, test_client):
        """Test importing an empty backup."""
        backup = make_valid_backup()
        file_content = json.dumps(backup).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["categories_created"] == 0
        assert data["tags_created"] == 0
        assert data["articles_created"] == 0

    @pytest.mark.asyncio
    async def test_import_categories(self, test_client):
        """Test importing categories."""
        backup = make_valid_backup(
            categories=[
                {"name": "Science", "parent_name": None, "description": None, "position": 0},
                {"name": "Physics", "parent_name": "Science", "description": None, "position": 0},
            ]
        )
        file_content = json.dumps(backup).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["categories_created"] == 2

        # Verify categories exist
        list_response = await test_client.get("/api/categories")
        categories = list_response.json()
        assert len(categories) == 1  # Science at root
        assert categories[0]["name"] == "Science"
        assert len(categories[0]["children"]) == 1
        assert categories[0]["children"][0]["name"] == "Physics"

    @pytest.mark.asyncio
    async def test_import_tags(self, test_client):
        """Test importing tags."""
        backup = make_valid_backup(
            tags=[
                {"name": "python", "color": "#3776AB"},
                {"name": "rust", "color": "#DEA584"},
            ]
        )
        file_content = json.dumps(backup).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tags_created"] == 2

    @pytest.mark.asyncio
    async def test_import_articles(self, test_client):
        """Test importing articles."""
        backup = make_valid_backup(
            articles=[
                {
                    "original_url": "https://example.com/imported",
                    "title": "Imported Article",
                    "authors": ["John Doe"],
                    "publication_date": None,
                    "source_type": "url",
                    "summary": "A summary",
                    "summary_model": None,
                    "extracted_text": "Article content",
                    "word_count": 2,
                    "is_read": False,
                    "metadata": {},
                    "category_names": [],
                    "tag_names": [],
                    "notes": [],
                    "created_at": "2025-01-15T10:00:00",
                    "updated_at": "2025-01-15T10:00:00",
                }
            ]
        )
        file_content = json.dumps(backup).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["articles_created"] == 1

    @pytest.mark.asyncio
    async def test_import_skips_duplicates(self, test_client, test_article):
        """Test importing skips articles with duplicate URLs."""
        backup = make_valid_backup(
            articles=[
                {
                    "original_url": test_article.original_url,  # Same URL as existing
                    "title": "Duplicate Article",
                    "authors": [],
                    "publication_date": None,
                    "source_type": "url",
                    "summary": None,
                    "summary_model": None,
                    "extracted_text": "content",
                    "word_count": 1,
                    "is_read": False,
                    "metadata": {},
                    "category_names": [],
                    "tag_names": [],
                    "notes": [],
                    "created_at": "2025-01-15T10:00:00",
                    "updated_at": "2025-01-15T10:00:00",
                }
            ]
        )
        file_content = json.dumps(backup).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["articles_created"] == 0
        assert data["articles_skipped"] == 1

    @pytest.mark.asyncio
    async def test_import_invalid_json(self, test_client):
        """Test importing invalid JSON returns error."""
        file_content = b"not valid json {"

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 400
        assert "invalid json" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_import_invalid_format(self, test_client):
        """Test importing JSON without required fields returns error."""
        file_content = json.dumps({"foo": "bar"}).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 400
        assert "invalid backup" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_import_wrong_file_type(self, test_client):
        """Test importing non-JSON file returns error."""
        file_content = b"plain text content"

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.txt", BytesIO(file_content), "text/plain")},
        )

        assert response.status_code == 400
        assert "json" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_import_with_notes(self, test_client):
        """Test importing articles with notes."""
        backup = make_valid_backup(
            articles=[
                {
                    "original_url": "https://example.com/with-notes",
                    "title": "Article With Notes",
                    "authors": [],
                    "publication_date": None,
                    "source_type": "url",
                    "summary": None,
                    "summary_model": None,
                    "extracted_text": "content",
                    "word_count": 1,
                    "is_read": False,
                    "metadata": {},
                    "category_names": [],
                    "tag_names": [],
                    "notes": [
                        {
                            "content": "First note",
                            "created_at": "2025-01-15T10:00:00",
                            "updated_at": "2025-01-15T10:00:00",
                        },
                        {
                            "content": "Second note",
                            "created_at": "2025-01-15T11:00:00",
                            "updated_at": "2025-01-15T11:00:00",
                        },
                    ],
                    "created_at": "2025-01-15T10:00:00",
                    "updated_at": "2025-01-15T10:00:00",
                }
            ]
        )
        file_content = json.dumps(backup).encode()

        response = await test_client.post(
            "/api/library/import",
            files={"file": ("backup.json", BytesIO(file_content), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["articles_created"] == 1
        assert data["notes_created"] == 2
