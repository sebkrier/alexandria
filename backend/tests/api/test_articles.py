"""
Tests for the articles API endpoints.

Coverage target: 75%+ of app/api/routes/articles.py
"""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from app.models.article import ProcessingStatus, SourceType


@pytest_asyncio.fixture
async def multiple_articles(async_db_session, test_user):
    """Create multiple test articles."""
    from app.models.article import Article

    articles = []
    for i in range(5):
        article = Article(
            user_id=test_user.id,
            source_type=SourceType.URL,
            original_url=f"https://example.com/article-{i}",
            title=f"Test Article {i}",
            extracted_text=f"Content for article {i}",
            word_count=100 + i * 10,
            processing_status=ProcessingStatus.COMPLETED,
            summary=f"Summary {i}",
            is_read=(i % 2 == 0),  # Alternate read/unread
        )
        async_db_session.add(article)
        articles.append(article)

    await async_db_session.commit()
    for a in articles:
        await async_db_session.refresh(a)
    return articles


class TestCreateArticleFromURL:
    """Tests for POST /api/articles endpoint."""

    @pytest.mark.asyncio
    async def test_create_article_success(self, test_client):
        """Test creating an article from URL."""
        from tests.api.conftest import make_extracted_content

        with patch("app.api.routes.articles.extract_content") as mock_extract:
            mock_extract.return_value = make_extracted_content()
            with patch("app.api.routes.articles.process_article_background"):
                response = await test_client.post(
                    "/api/articles",
                    json={"url": "https://example.com/test-article"},
                )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Article"
        assert data["source_type"] == "url"
        assert data["processing_status"] == "pending"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_article_extraction_failure(self, test_client):
        """Test article creation fails when extraction fails."""
        with patch("app.api.routes.articles.extract_content") as mock_extract:
            mock_extract.side_effect = Exception("Failed to extract content")
            response = await test_client.post(
                "/api/articles",
                json={"url": "https://example.com/bad-url"},
            )

        assert response.status_code == 400
        assert "failed to extract" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_article_invalid_url(self, test_client):
        """Test article creation with invalid URL."""
        response = await test_client.post(
            "/api/articles",
            json={"url": "not-a-valid-url"},
        )

        assert response.status_code == 422  # Pydantic validation error


class TestCreateArticleFromUpload:
    """Tests for POST /api/articles/upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_pdf_success(self, test_client):
        """Test uploading a PDF file."""
        # Create a mock PDF content
        pdf_content = b"%PDF-1.4 mock pdf content"

        with patch("app.api.routes.articles.extract_content") as mock_extract:
            from tests.api.conftest import make_extracted_content

            mock_extract.return_value = make_extracted_content(
                title="PDF Article",
                source_type="pdf",
            )

            with patch("app.api.routes.articles.process_article_background"):
                response = await test_client.post(
                    "/api/articles/upload",
                    files={"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")},
                )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "PDF Article"
        assert data["source_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_upload_non_pdf_rejected(self, test_client):
        """Test uploading non-PDF file is rejected."""
        txt_content = b"This is a text file"

        response = await test_client.post(
            "/api/articles/upload",
            files={"file": ("test.txt", BytesIO(txt_content), "text/plain")},
        )

        assert response.status_code == 400
        assert "pdf" in response.json()["detail"].lower()


class TestListArticles:
    """Tests for GET /api/articles endpoint."""

    @pytest.mark.asyncio
    async def test_list_articles_empty(self, test_client):
        """Test listing articles when none exist."""
        response = await test_client.get("/api/articles")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_articles_with_data(self, test_client, test_article):
        """Test listing articles returns existing articles."""
        response = await test_client.get("/api/articles")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == test_article.title
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_articles_pagination(self, test_client, multiple_articles):
        """Test article list pagination."""
        response = await test_client.get("/api/articles?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_search(self, test_client, multiple_articles):
        """Test filtering articles by search term."""
        response = await test_client.get("/api/articles?search=Article 2")

        assert response.status_code == 200
        data = response.json()
        # Should find "Test Article 2"
        assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_category(
        self, test_client, test_article, test_category, async_db_session
    ):
        """Test filtering articles by category."""
        from app.models.article_category import ArticleCategory

        # Associate article with category
        ac = ArticleCategory(
            article_id=test_article.id,
            category_id=test_category.id,
            is_primary=True,
        )
        async_db_session.add(ac)
        await async_db_session.commit()

        response = await test_client.get(f"/api/articles?category_id={test_category.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(test_article.id)

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_tag(
        self, test_client, test_article, test_tag, async_db_session
    ):
        """Test filtering articles by tag."""
        from app.models.article_tag import ArticleTag

        # Associate article with tag
        at = ArticleTag(article_id=test_article.id, tag_id=test_tag.id)
        async_db_session.add(at)
        await async_db_session.commit()

        response = await test_client.get(f"/api/articles?tag_id={test_tag.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_status(self, test_client, async_db_session, test_user):
        """Test filtering articles by processing status."""
        from app.models.article import Article

        # Create a pending article
        pending = Article(
            user_id=test_user.id,
            source_type=SourceType.URL,
            title="Pending Article",
            extracted_text="content",
            processing_status=ProcessingStatus.PENDING,
        )
        async_db_session.add(pending)
        await async_db_session.commit()

        response = await test_client.get("/api/articles?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["processing_status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_is_read(self, test_client, multiple_articles):
        """Test filtering articles by read status."""
        response = await test_client.get("/api/articles?is_read=false")

        assert response.status_code == 200
        data = response.json()
        # Only unread articles (indices 1, 3 from fixture)
        for item in data["items"]:
            assert item["is_read"] is False

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_color(
        self, test_client, test_article, test_color, async_db_session
    ):
        """Test filtering articles by color."""
        test_article.color_id = test_color.id
        await async_db_session.commit()

        response = await test_client.get(f"/api/articles?color_id={test_color.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1


class TestGetArticle:
    """Tests for GET /api/articles/{article_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_article_success(self, test_client, test_article):
        """Test getting a single article."""
        response = await test_client.get(f"/api/articles/{test_article.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_article.id)
        assert data["title"] == test_article.title

    @pytest.mark.asyncio
    async def test_get_article_not_found(self, test_client):
        """Test getting non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.get(f"/api/articles/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_article_wrong_user(self, test_client, async_db_session):
        """Test user cannot get another user's article."""
        from app.models.article import Article
        from app.models.user import User

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

        response = await test_client.get(f"/api/articles/{other_article.id}")

        assert response.status_code == 404


class TestGetArticleText:
    """Tests for GET /api/articles/{article_id}/text endpoint."""

    @pytest.mark.asyncio
    async def test_get_article_text_success(self, test_client, test_article):
        """Test getting article extracted text."""
        response = await test_client.get(f"/api/articles/{test_article.id}/text")

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == test_article.extracted_text

    @pytest.mark.asyncio
    async def test_get_article_text_not_found(self, test_client):
        """Test getting text for non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.get(f"/api/articles/{fake_id}/text")

        assert response.status_code == 404


class TestUnreadReader:
    """Tests for unread reader endpoints."""

    @pytest.mark.asyncio
    async def test_get_unread_list(self, test_client, multiple_articles):
        """Test getting list of unread article IDs."""
        response = await test_client.get("/api/articles/unread/list")

        assert response.status_code == 200
        data = response.json()
        # Should have unread articles (indices 1, 3 from fixture)
        assert data["total"] >= 2
        assert len(data["items"]) == data["total"]

    @pytest.mark.asyncio
    async def test_get_unread_list_empty(self, test_client):
        """Test getting unread list when no articles exist."""
        response = await test_client.get("/api/articles/unread/list")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_unread_navigation(self, test_client, async_db_session, test_user):
        """Test getting navigation for unread reader."""
        from app.models.article import Article

        # Create 3 unread articles
        articles = []
        for i in range(3):
            a = Article(
                user_id=test_user.id,
                source_type=SourceType.URL,
                title=f"Unread {i}",
                extracted_text="content",
                processing_status=ProcessingStatus.COMPLETED,
                is_read=False,
            )
            async_db_session.add(a)
            articles.append(a)

        await async_db_session.commit()
        for a in articles:
            await async_db_session.refresh(a)

        # Get navigation for middle article
        response = await test_client.get(f"/api/articles/unread/navigation/{articles[1].id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total_unread"] == 3
        assert data["current_position"] == 2  # 1-indexed
        assert data["prev_id"] == str(articles[0].id)
        assert data["next_id"] == str(articles[2].id)


class TestUpdateArticle:
    """Tests for PATCH /api/articles/{article_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_article_title(self, test_client, test_article):
        """Test updating article title."""
        response = await test_client.patch(
            f"/api/articles/{test_article.id}",
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_article_is_read(self, test_client, test_article):
        """Test marking article as read."""
        response = await test_client.patch(
            f"/api/articles/{test_article.id}",
            json={"is_read": True},
        )

        assert response.status_code == 200
        assert response.json()["is_read"] is True

    @pytest.mark.asyncio
    async def test_update_article_color(self, test_client, test_article, test_color):
        """Test updating article color."""
        response = await test_client.patch(
            f"/api/articles/{test_article.id}",
            json={"color_id": str(test_color.id)},
        )

        assert response.status_code == 200
        assert response.json()["color_id"] == str(test_color.id)

    @pytest.mark.asyncio
    async def test_update_article_categories(self, test_client, test_article, test_category):
        """Test updating article categories."""
        response = await test_client.patch(
            f"/api/articles/{test_article.id}",
            json={"category_ids": [str(test_category.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["categories"]) == 1
        assert data["categories"][0]["id"] == str(test_category.id)

    @pytest.mark.asyncio
    async def test_update_article_tags(self, test_client, test_article, test_tag):
        """Test updating article tags."""
        response = await test_client.patch(
            f"/api/articles/{test_article.id}",
            json={"tag_ids": [str(test_tag.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) == 1
        assert data["tags"][0]["id"] == str(test_tag.id)

    @pytest.mark.asyncio
    async def test_update_article_not_found(self, test_client):
        """Test updating non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.patch(
            f"/api/articles/{fake_id}",
            json={"title": "New Title"},
        )

        assert response.status_code == 404


class TestDeleteArticle:
    """Tests for DELETE /api/articles/{article_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_article_success(self, test_client, test_article):
        """Test deleting an article."""
        response = await test_client.delete(f"/api/articles/{test_article.id}")

        assert response.status_code == 204

        # Verify deleted
        get_response = await test_client.get(f"/api/articles/{test_article.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_article_not_found(self, test_client):
        """Test deleting non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.delete(f"/api/articles/{fake_id}")

        assert response.status_code == 404


class TestProcessArticle:
    """Tests for POST /api/articles/{article_id}/process endpoint."""

    @pytest.mark.asyncio
    async def test_process_article_success(self, test_client, test_article):
        """Test processing an article with AI."""
        with patch("app.api.routes.articles.AIService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.process_article = AsyncMock(return_value=test_article)
            mock_service_class.return_value = mock_service

            response = await test_client.post(f"/api/articles/{test_article.id}/process")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_process_article_not_found(self, test_client):
        """Test processing non-existent article returns 404."""
        fake_id = uuid4()
        response = await test_client.post(f"/api/articles/{fake_id}/process")

        assert response.status_code == 404


class TestBulkOperations:
    """Tests for bulk article operations."""

    @pytest.mark.asyncio
    async def test_bulk_delete_success(self, test_client, multiple_articles):
        """Test bulk deleting articles."""
        ids_to_delete = [str(a.id) for a in multiple_articles[:2]]

        response = await test_client.post(
            "/api/articles/bulk/delete",
            json={"article_ids": ids_to_delete},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 2
        assert data["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_delete_partial_failure(self, test_client, test_article):
        """Test bulk delete with some non-existent IDs."""
        response = await test_client.post(
            "/api/articles/bulk/delete",
            json={"article_ids": [str(test_article.id), str(uuid4())]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 1
        assert len(data["failed"]) == 1

    @pytest.mark.asyncio
    async def test_bulk_update_color(self, test_client, multiple_articles, test_color):
        """Test bulk updating article colors."""
        ids = [str(a.id) for a in multiple_articles[:3]]

        response = await test_client.patch(
            "/api/articles/bulk/color",
            json={"article_ids": ids, "color_id": str(test_color.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 3
        assert data["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_reanalyze(self, test_client, multiple_articles):
        """Test bulk reanalyzing articles."""
        ids = [str(a.id) for a in multiple_articles[:2]]

        with patch("app.api.routes.articles.AIService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.process_article = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            response = await test_client.post(
                "/api/articles/bulk/reanalyze",
                json={"article_ids": ids},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["queued"] == 2


class TestAskQuestion:
    """Tests for POST /api/articles/ask endpoint."""

    @pytest.mark.asyncio
    async def test_ask_question_no_provider(self, test_client):
        """Test asking question without configured provider."""
        with patch("app.api.routes.articles.get_default_provider") as mock:
            mock.return_value = None

            response = await test_client.post(
                "/api/articles/ask",
                json={"question": "What do my articles say about AI?"},
            )

        assert response.status_code == 400
        assert "provider" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_ask_content_question(self, test_client, test_article):
        """Test asking a content-based question (RAG)."""
        mock_provider = AsyncMock()
        mock_provider.answer_question = AsyncMock(
            return_value="Based on your articles, AI is transforming industries."
        )

        with patch("app.api.routes.articles.get_default_provider") as mock_get:
            mock_get.return_value = mock_provider
            with patch("app.api.routes.articles.classify_query") as mock_classify:
                from app.ai.query_router import QueryType

                mock_classify.return_value = QueryType.CONTENT
                with patch("app.api.routes.articles.generate_query_embedding") as mock_embed:
                    mock_embed.return_value = [0.1] * 768

                    response = await test_client.post(
                        "/api/articles/ask",
                        json={"question": "What do my articles say about AI?"},
                    )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "articles" in data

    @pytest.mark.asyncio
    async def test_ask_metadata_question(self, test_client, test_article):
        """Test asking a metadata-based question."""
        mock_provider = AsyncMock()
        mock_provider.answer_question = AsyncMock(
            return_value="You have 1 article in your library."
        )

        with patch("app.api.routes.articles.get_default_provider") as mock_get:
            mock_get.return_value = mock_provider
            with patch("app.api.routes.articles.classify_query") as mock_classify:
                from app.ai.query_router import QueryType

                mock_classify.return_value = QueryType.METADATA
                with patch("app.api.routes.articles.detect_metadata_operation") as mock_detect:
                    from app.ai.query_router import MetadataOperation

                    mock_detect.return_value = (MetadataOperation.TOTAL_COUNT, {})
                    with patch("app.api.routes.articles.execute_metadata_query") as mock_exec:
                        mock_exec.return_value = {"count": 1}
                        with patch(
                            "app.api.routes.articles.format_metadata_for_llm"
                        ) as mock_format:
                            mock_format.return_value = "Total articles: 1"

                            response = await test_client.post(
                                "/api/articles/ask",
                                json={"question": "How many articles do I have?"},
                            )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data


class TestHelperFunctions:
    """Tests for helper functions in articles module."""

    def test_calculate_reading_time(self):
        """Test reading time calculation."""
        from app.api.routes.articles import calculate_reading_time

        assert calculate_reading_time(200) == 1  # 1 minute
        assert calculate_reading_time(400) == 2  # 2 minutes
        assert calculate_reading_time(50) == 1  # Minimum 1 minute
        assert calculate_reading_time(None) is None

    def test_determine_media_type_arxiv(self):
        """Test media type detection for arXiv."""
        from app.api.routes.articles import determine_media_type
        from app.schemas.article import MediaType

        result = determine_media_type(SourceType.ARXIV, "https://arxiv.org/abs/123")
        assert result == MediaType.PAPER

    def test_determine_media_type_video(self):
        """Test media type detection for video."""
        from app.api.routes.articles import determine_media_type
        from app.schemas.article import MediaType

        result = determine_media_type(SourceType.VIDEO, "https://youtube.com/watch?v=123")
        assert result == MediaType.VIDEO

    def test_determine_media_type_pdf(self):
        """Test media type detection for PDF."""
        from app.api.routes.articles import determine_media_type
        from app.schemas.article import MediaType

        result = determine_media_type(SourceType.PDF, None)
        assert result == MediaType.PDF

    def test_determine_media_type_substack(self):
        """Test media type detection for newsletter."""
        from app.api.routes.articles import determine_media_type
        from app.schemas.article import MediaType

        result = determine_media_type(SourceType.URL, "https://example.substack.com/p/my-post")
        assert result == MediaType.NEWSLETTER

    def test_determine_media_type_blog(self):
        """Test media type detection for blog."""
        from app.api.routes.articles import determine_media_type
        from app.schemas.article import MediaType

        result = determine_media_type(SourceType.URL, "https://medium.com/article")
        assert result == MediaType.BLOG

    def test_determine_media_type_default(self):
        """Test default media type is article."""
        from app.api.routes.articles import determine_media_type
        from app.schemas.article import MediaType

        result = determine_media_type(SourceType.URL, "https://example.com/page")
        assert result == MediaType.ARTICLE
