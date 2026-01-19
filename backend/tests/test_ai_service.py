"""
Tests for the AI Service (app/ai/service.py).

Tests the core article processing pipeline including:
- Summary generation
- Tag suggestion and application
- Category suggestion and application
- Embedding generation
- Error handling and status updates
"""

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.ai.base import CategoryInfo, CategorySuggestion, TagSuggestion
from app.ai.service import AIService
from app.models.article import Article, ProcessingStatus

# =============================================================================
# Happy Path Tests
# =============================================================================


@pytest.mark.asyncio
async def test_process_article_success(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    sample_summary_markdown,
    sample_tags_json,
    sample_category_json,
    mock_litellm,
):
    """Test successful article processing with summary, tags, and category."""
    from tests.conftest import MockLiteLLMResponse

    # Setup mock responses in sequence: summary, tags, category
    mock_litellm.side_effect = [
        MockLiteLLMResponse(sample_summary_markdown),
        MockLiteLLMResponse(sample_tags_json),
        MockLiteLLMResponse(sample_category_json),
    ]

    # Mock embedding generation to avoid model loading
    with patch("app.ai.service.generate_embedding", return_value=[0.1] * 768):
        service = AIService(async_db_session)
        article = await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify article was processed
    assert article.processing_status == ProcessingStatus.COMPLETED
    assert article.processing_error is None
    assert article.summary is not None
    assert "machine learning transformers" in article.summary.lower()


@pytest.mark.asyncio
async def test_process_article_updates_status_to_completed(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    mock_litellm,
):
    """Test that article status ends up as COMPLETED after processing."""
    from tests.conftest import MockLiteLLMResponse

    # Verify initial status
    assert test_article_for_processing.processing_status == ProcessingStatus.PENDING

    mock_litellm.side_effect = [
        MockLiteLLMResponse("## One-Line Summary\nTest summary."),
        MockLiteLLMResponse('[{"name": "test", "confidence": 0.9, "reasoning": "test"}]'),
        MockLiteLLMResponse(
            '{"category": {"name": "Test", "is_new": true}, '
            '"subcategory": {"name": "Sub", "is_new": true}, '
            '"confidence": 0.8, "reasoning": "test"}'
        ),
    ]

    with patch("app.ai.service.generate_embedding", return_value=None):
        service = AIService(async_db_session)
        article = await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Final status should be COMPLETED
    assert article.processing_status == ProcessingStatus.COMPLETED
    assert article.processing_error is None


@pytest.mark.asyncio
async def test_process_article_with_existing_tags(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    test_tag,
    mock_litellm,
):
    """Test that existing tags are reused when AI suggests matching names."""
    from tests.conftest import MockLiteLLMResponse

    # AI suggests a tag that already exists
    existing_tag_name = test_tag.name  # "test-tag" from fixture

    mock_litellm.side_effect = [
        MockLiteLLMResponse("## One-Line Summary\nTest summary."),
        MockLiteLLMResponse(
            f'[{{"name": "{existing_tag_name}", "confidence": 0.95, "reasoning": "Matches existing"}}]'
        ),
        MockLiteLLMResponse(
            '{"category": {"name": "Test", "is_new": true}, '
            '"subcategory": {"name": "Sub", "is_new": true}, '
            '"confidence": 0.8, "reasoning": "test"}'
        ),
    ]

    with patch("app.ai.service.generate_embedding", return_value=None):
        service = AIService(async_db_session)
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify the existing tag was used (no new tag with same name created)
    from sqlalchemy import select

    from app.models.tag import Tag

    result = await async_db_session.execute(
        select(Tag).where(Tag.user_id == test_user.id, Tag.name == existing_tag_name)
    )
    tags = result.scalars().all()
    assert len(tags) == 1  # Only one tag with this name


@pytest.mark.asyncio
async def test_process_article_creates_new_category(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    mock_litellm,
):
    """Test that new categories are created when AI suggests them."""
    from tests.conftest import MockLiteLLMResponse

    new_category_name = "New AI Category"
    new_subcategory_name = "New Subcategory"

    mock_litellm.side_effect = [
        MockLiteLLMResponse("## One-Line Summary\nTest summary."),
        MockLiteLLMResponse('[{"name": "test", "confidence": 0.9, "reasoning": "test"}]'),
        MockLiteLLMResponse(
            f'{{"category": {{"name": "{new_category_name}", "is_new": true}}, '
            f'"subcategory": {{"name": "{new_subcategory_name}", "is_new": true}}, '
            f'"confidence": 0.85, "reasoning": "New category needed"}}'
        ),
    ]

    with patch("app.ai.service.generate_embedding", return_value=None):
        service = AIService(async_db_session)
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify new categories were created
    from sqlalchemy import select

    from app.models.category import Category

    parent_result = await async_db_session.execute(
        select(Category).where(
            Category.user_id == test_user.id,
            Category.name == new_category_name,
            Category.parent_id.is_(None),
        )
    )
    parent = parent_result.scalar_one_or_none()
    assert parent is not None

    child_result = await async_db_session.execute(
        select(Category).where(
            Category.user_id == test_user.id,
            Category.name == new_subcategory_name,
            Category.parent_id == parent.id,
        )
    )
    child = child_result.scalar_one_or_none()
    assert child is not None


@pytest.mark.asyncio
async def test_process_article_uses_existing_category(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    test_category,
    mock_litellm,
):
    """Test that existing categories are reused."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.side_effect = [
        MockLiteLLMResponse("## One-Line Summary\nTest summary."),
        MockLiteLLMResponse('[{"name": "test", "confidence": 0.9, "reasoning": "test"}]'),
        MockLiteLLMResponse(
            f'{{"category": {{"name": "{test_category.name}", "is_new": false}}, '
            f'"subcategory": {{"name": "New Sub", "is_new": true}}, '
            f'"confidence": 0.9, "reasoning": "Using existing category"}}'
        ),
    ]

    with patch("app.ai.service.generate_embedding", return_value=None):
        service = AIService(async_db_session)
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify subcategory was created under existing parent
    from sqlalchemy import select

    from app.models.category import Category

    result = await async_db_session.execute(
        select(Category).where(
            Category.user_id == test_user.id,
            Category.name == "New Sub",
            Category.parent_id == test_category.id,
        )
    )
    subcategory = result.scalar_one_or_none()
    assert subcategory is not None


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_process_article_not_found(async_db_session, test_user):
    """Test processing non-existent article raises ValueError."""
    service = AIService(async_db_session)

    with pytest.raises(ValueError, match="not found"):
        await service.process_article(
            article_id=uuid4(),  # Non-existent ID
            user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_process_article_no_provider(
    async_db_session, test_user, test_article_for_processing
):
    """Test processing without AI provider raises ValueError."""
    # No test_ai_provider fixture = no provider configured
    service = AIService(async_db_session)

    with pytest.raises(ValueError, match="No AI provider configured"):
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify status was set to FAILED
    await async_db_session.refresh(test_article_for_processing)
    assert test_article_for_processing.processing_status == ProcessingStatus.FAILED


@pytest.mark.asyncio
async def test_process_article_provider_error(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    mock_litellm,
):
    """Test that provider errors are handled gracefully."""
    # Simulate API error
    mock_litellm.side_effect = Exception("API rate limit exceeded")

    service = AIService(async_db_session)

    with pytest.raises(Exception, match="rate limit"):
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify status was set to FAILED with error message
    await async_db_session.refresh(test_article_for_processing)
    assert test_article_for_processing.processing_status == ProcessingStatus.FAILED
    assert "rate limit" in test_article_for_processing.processing_error


@pytest.mark.asyncio
async def test_process_article_low_confidence_tags_skipped(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    mock_litellm,
):
    """Test that low-confidence tags (< 0.7) are not applied."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.side_effect = [
        MockLiteLLMResponse("## One-Line Summary\nTest summary."),
        MockLiteLLMResponse(
            "["
            '{"name": "high-conf", "confidence": 0.9, "reasoning": "Good match"},'
            '{"name": "low-conf", "confidence": 0.5, "reasoning": "Weak match"}'
            "]"
        ),
        MockLiteLLMResponse(
            '{"category": {"name": "Test", "is_new": true}, '
            '"subcategory": {"name": "Sub", "is_new": true}, '
            '"confidence": 0.8, "reasoning": "test"}'
        ),
    ]

    with patch("app.ai.service.generate_embedding", return_value=None):
        service = AIService(async_db_session)
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify only high-confidence tag was created
    from sqlalchemy import select

    from app.models.tag import Tag

    high_conf = await async_db_session.execute(
        select(Tag).where(Tag.user_id == test_user.id, Tag.name == "high-conf")
    )
    assert high_conf.scalar_one_or_none() is not None

    low_conf = await async_db_session.execute(
        select(Tag).where(Tag.user_id == test_user.id, Tag.name == "low-conf")
    )
    assert low_conf.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_process_article_low_confidence_category_skipped(
    async_db_session,
    test_user,
    test_article_for_processing,
    test_ai_provider,
    mock_litellm,
):
    """Test that low-confidence categories (< 0.5) are not applied."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.side_effect = [
        MockLiteLLMResponse("## One-Line Summary\nTest summary."),
        MockLiteLLMResponse('[{"name": "test", "confidence": 0.9, "reasoning": "test"}]'),
        MockLiteLLMResponse(
            '{"category": {"name": "LowConf", "is_new": true}, '
            '"subcategory": {"name": "Sub", "is_new": true}, '
            '"confidence": 0.3, "reasoning": "Low confidence"}'  # Below 0.5 threshold
        ),
    ]

    with patch("app.ai.service.generate_embedding", return_value=None):
        service = AIService(async_db_session)
        await service.process_article(
            article_id=test_article_for_processing.id,
            user_id=test_user.id,
        )

    # Verify category was NOT created
    from sqlalchemy import select

    from app.models.category import Category

    result = await async_db_session.execute(
        select(Category).where(Category.user_id == test_user.id, Category.name == "LowConf")
    )
    assert result.scalar_one_or_none() is None


# =============================================================================
# Component Tests - _apply_tags
# =============================================================================


@pytest.mark.asyncio
async def test_apply_tags_creates_new_tags(async_db_session, test_user, test_article):
    """Test that _apply_tags creates new tags when they don't exist."""
    service = AIService(async_db_session)

    suggestions = [
        TagSuggestion(name="new-tag-1", confidence=0.9, reasoning="Test"),
        TagSuggestion(name="new-tag-2", confidence=0.85, reasoning="Test"),
    ]

    await service._apply_tags(test_article, test_user.id, suggestions)
    await async_db_session.commit()

    # Verify tags were created
    from sqlalchemy import select

    from app.models.tag import Tag

    for name in ["new-tag-1", "new-tag-2"]:
        result = await async_db_session.execute(
            select(Tag).where(Tag.user_id == test_user.id, Tag.name == name)
        )
        assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_apply_tags_reuses_existing_tags(async_db_session, test_user, test_article, test_tag):
    """Test that _apply_tags reuses existing tags."""
    from sqlalchemy import func, select

    from app.models.tag import Tag

    service = AIService(async_db_session)

    # Count tags before
    count_before = await async_db_session.execute(
        select(func.count()).select_from(Tag).where(Tag.user_id == test_user.id)
    )
    before = count_before.scalar()

    suggestions = [
        TagSuggestion(name=test_tag.name, confidence=0.9, reasoning="Existing tag"),
    ]

    await service._apply_tags(test_article, test_user.id, suggestions)
    await async_db_session.commit()

    # Count should not increase
    count_after = await async_db_session.execute(
        select(func.count()).select_from(Tag).where(Tag.user_id == test_user.id)
    )
    after = count_after.scalar()

    assert after == before


@pytest.mark.asyncio
async def test_apply_tags_max_seven_tags(async_db_session, test_user, test_article):
    """Test that only first 7 high-confidence tags are applied."""
    service = AIService(async_db_session)

    # Create 10 high-confidence suggestions
    suggestions = [
        TagSuggestion(name=f"tag-{i}", confidence=0.9, reasoning="Test") for i in range(10)
    ]

    await service._apply_tags(test_article, test_user.id, suggestions)
    await async_db_session.commit()

    # Verify only 7 tags were created
    from sqlalchemy import func, select

    from app.models.article_tag import ArticleTag

    result = await async_db_session.execute(
        select(func.count()).select_from(ArticleTag).where(ArticleTag.article_id == test_article.id)
    )
    assert result.scalar() == 7


# =============================================================================
# Component Tests - _apply_category
# =============================================================================


@pytest.mark.asyncio
async def test_apply_category_creates_hierarchy(async_db_session, test_user, test_article):
    """Test that _apply_category creates parent and child categories."""
    service = AIService(async_db_session)

    suggestion = CategorySuggestion(
        category=CategoryInfo(name="Parent Cat", is_new=True),
        subcategory=CategoryInfo(name="Child Cat", is_new=True),
        confidence=0.9,
        reasoning="Test hierarchy",
    )

    await service._apply_category(test_article, test_user.id, suggestion)
    await async_db_session.commit()

    # Verify hierarchy
    from sqlalchemy import select

    from app.models.category import Category

    parent = await async_db_session.execute(
        select(Category).where(
            Category.user_id == test_user.id,
            Category.name == "Parent Cat",
            Category.parent_id.is_(None),
        )
    )
    parent_cat = parent.scalar_one()

    child = await async_db_session.execute(
        select(Category).where(
            Category.user_id == test_user.id,
            Category.name == "Child Cat",
            Category.parent_id == parent_cat.id,
        )
    )
    assert child.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_apply_category_removes_old_assignments(
    async_db_session, test_user, test_article, test_category
):
    """Test that _apply_category removes previous category assignments."""
    from app.models.article_category import ArticleCategory

    # First, assign article to existing category
    initial_assignment = ArticleCategory(
        article_id=test_article.id,
        category_id=test_category.id,
        is_primary=True,
    )
    async_db_session.add(initial_assignment)
    await async_db_session.commit()

    service = AIService(async_db_session)

    # Now apply a new category
    suggestion = CategorySuggestion(
        category=CategoryInfo(name="New Parent", is_new=True),
        subcategory=CategoryInfo(name="New Child", is_new=True),
        confidence=0.9,
        reasoning="Reassignment",
    )

    await service._apply_category(test_article, test_user.id, suggestion)
    await async_db_session.commit()

    # Verify only one category assignment exists
    from sqlalchemy import func, select

    result = await async_db_session.execute(
        select(func.count())
        .select_from(ArticleCategory)
        .where(ArticleCategory.article_id == test_article.id)
    )
    assert result.scalar() == 1


# =============================================================================
# Component Tests - _generate_article_embedding
# =============================================================================


@pytest.mark.asyncio
async def test_generate_article_embedding_success(
    async_db_session, test_article, mock_embedding_model
):
    """Test embedding generation for article."""
    service = AIService(async_db_session)

    embedding = service._generate_article_embedding(test_article)

    assert embedding is not None
    assert len(embedding) == 768
    assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_generate_article_embedding_empty_content(async_db_session, test_user):
    """Test embedding generation with no content returns None."""
    from app.models.article import ProcessingStatus, SourceType

    # Create article with no content
    empty_article = Article(
        user_id=test_user.id,
        source_type=SourceType.URL,
        title=None,
        summary=None,
        extracted_text=None,
        processing_status=ProcessingStatus.PENDING,
    )

    service = AIService(async_db_session)
    embedding = service._generate_article_embedding(empty_article)

    assert embedding is None


@pytest.mark.asyncio
async def test_generate_article_embedding_error_handling(async_db_session, test_article):
    """Test embedding generation handles errors gracefully."""
    with patch("app.ai.service.generate_embedding", side_effect=Exception("Model error")):
        service = AIService(async_db_session)
        embedding = service._generate_article_embedding(test_article)

    assert embedding is None  # Should return None, not raise


# =============================================================================
# Regenerate Summary Tests
# =============================================================================


@pytest.mark.asyncio
async def test_regenerate_summary_success(
    async_db_session,
    test_user,
    test_article,
    test_ai_provider,
    mock_litellm,
    sample_summary_markdown,
):
    """Test regenerating summary for existing article."""
    from tests.conftest import MockLiteLLMResponse

    mock_litellm.return_value = MockLiteLLMResponse(sample_summary_markdown)

    service = AIService(async_db_session)
    summary = await service.regenerate_summary(
        article_id=test_article.id,
        user_id=test_user.id,
    )

    assert summary is not None
    assert summary.abstract  # Should have extracted abstract
    await async_db_session.refresh(test_article)
    assert test_article.summary is not None


@pytest.mark.asyncio
async def test_regenerate_summary_article_not_found(async_db_session, test_user):
    """Test regenerating summary for non-existent article."""
    service = AIService(async_db_session)

    with pytest.raises(ValueError, match="not found"):
        await service.regenerate_summary(
            article_id=uuid4(),
            user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_regenerate_summary_no_provider(async_db_session, test_user, test_article):
    """Test regenerating summary without provider configured."""
    service = AIService(async_db_session)

    with pytest.raises(ValueError, match="No AI provider"):
        await service.regenerate_summary(
            article_id=test_article.id,
            user_id=test_user.id,
        )


# =============================================================================
# Helper Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_existing_tags(async_db_session, test_user, test_tag):
    """Test _get_existing_tags returns user's tag names."""
    service = AIService(async_db_session)
    tags = await service._get_existing_tags(test_user.id)

    assert isinstance(tags, list)
    assert test_tag.name in tags


@pytest.mark.asyncio
async def test_get_existing_tags_empty(async_db_session, test_user):
    """Test _get_existing_tags returns empty list when no tags."""
    service = AIService(async_db_session)
    tags = await service._get_existing_tags(test_user.id)

    assert tags == []


@pytest.mark.asyncio
async def test_get_category_tree(async_db_session, test_user, test_category):
    """Test _get_category_tree returns category structure."""
    service = AIService(async_db_session)
    tree = await service._get_category_tree(test_user.id)

    assert isinstance(tree, list)
    assert len(tree) >= 1
    assert tree[0]["name"] == test_category.name


@pytest.mark.asyncio
async def test_get_category_tree_empty(async_db_session, test_user):
    """Test _get_category_tree returns empty list when no categories."""
    service = AIService(async_db_session)
    tree = await service._get_category_tree(test_user.id)

    assert tree == []


@pytest.mark.asyncio
async def test_get_category_tree_nested(async_db_session, test_user):
    """Test _get_category_tree returns nested structure."""
    from app.models.category import Category

    # Create parent
    parent = Category(user_id=test_user.id, name="Parent", position=0)
    async_db_session.add(parent)
    await async_db_session.commit()
    await async_db_session.refresh(parent)

    # Create child
    child = Category(user_id=test_user.id, name="Child", parent_id=parent.id, position=0)
    async_db_session.add(child)
    await async_db_session.commit()

    service = AIService(async_db_session)
    tree = await service._get_category_tree(test_user.id)

    assert len(tree) == 1
    assert tree[0]["name"] == "Parent"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["name"] == "Child"
