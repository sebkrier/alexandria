"""HTMX routes for taxonomy optimization (AI-powered category reorganization)."""

import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.article import Article
from app.models.article_category import ArticleCategory
from app.models.category import Category
from app.models.user import User
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Taxonomy Optimization Routes
# =============================================================================


@router.get("/taxonomy/optimize", response_class=HTMLResponse)
async def taxonomy_optimize_modal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Show the taxonomy optimization modal with loading state."""
    # Count articles
    result = await db.execute(
        select(func.count(Article.id)).where(Article.user_id == current_user.id)
    )
    article_count = result.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="partials/taxonomy_optimize_modal.html",
        context={
            "article_count": article_count,
            "loading": True,
        },
    )


@router.post("/taxonomy/analyze", response_class=HTMLResponse)
async def taxonomy_analyze(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Run AI analysis and return the preview of proposed changes."""
    from app.ai.factory import get_default_provider
    from app.ai.llm import LiteLLMProvider

    try:
        # Get AI provider
        provider = await get_default_provider(db, current_user.id)
        if not provider:
            return templates.TemplateResponse(
                request=request,
                name="partials/taxonomy_optimize_modal.html",
                context={
                    "error": "No AI provider configured. Please add one in Settings.",
                },
            )

        # Fetch all articles with their current categories
        result = await db.execute(
            select(Article)
            .where(Article.user_id == current_user.id)
            .options(selectinload(Article.categories).selectinload(ArticleCategory.category))
            .order_by(Article.created_at.desc())
        )
        articles = result.scalars().all()

        if not articles:
            return templates.TemplateResponse(
                request=request,
                name="partials/taxonomy_optimize_modal.html",
                context={
                    "error": "No articles in library to analyze.",
                },
            )

        # Prepare articles for AI analysis
        articles_for_ai = []
        for article in articles:
            current_cat = "Uncategorized"
            current_subcat = None

            # Get current category assignment
            if article.categories:
                for ac in article.categories:
                    if ac.category:
                        if ac.category.parent_id:
                            # This is a subcategory
                            current_subcat = ac.category.name
                            # Get parent
                            parent_result = await db.execute(
                                select(Category).where(Category.id == ac.category.parent_id)
                            )
                            parent = parent_result.scalar_one_or_none()
                            if parent:
                                current_cat = parent.name
                        else:
                            current_cat = ac.category.name

            articles_for_ai.append(
                {
                    "id": str(article.id),
                    "title": article.title or "Untitled",
                    "summary": article.summary or "",
                    "current_category": current_cat,
                    "current_subcategory": current_subcat,
                }
            )

        # Get current taxonomy structure
        async def get_category_tree(parent_id=None):
            result = await db.execute(
                select(Category)
                .where(
                    Category.user_id == current_user.id,
                    Category.parent_id == parent_id,
                )
                .order_by(Category.position)
            )
            cats = result.scalars().all()
            tree = []
            for cat in cats:
                children = await get_category_tree(cat.id)
                tree.append(
                    {
                        "name": cat.name,
                        "id": str(cat.id),
                        "children": children,
                    }
                )
            return tree

        current_taxonomy = await get_category_tree()

        # Call AI for taxonomy optimization
        if not isinstance(provider, LiteLLMProvider):
            return templates.TemplateResponse(
                request=request,
                name="partials/taxonomy_optimize_modal.html",
                context={
                    "error": "Provider does not support taxonomy optimization.",
                },
            )

        optimization_result = await provider.optimize_taxonomy(
            articles=articles_for_ai,
            current_taxonomy=current_taxonomy,
        )

        # Build article lookup for display
        article_lookup = {str(a.id): a for a in articles}

        # Convert taxonomy to JSON-serializable format for the hidden input
        taxonomy_for_json = [
            {
                "category": cat.category,
                "subcategories": [
                    {
                        "name": sub.name,
                        "article_ids": sub.article_ids,
                        "description": sub.description,
                    }
                    for sub in cat.subcategories
                ],
            }
            for cat in optimization_result.taxonomy
        ]
        taxonomy_json = json.dumps(taxonomy_for_json)

        return templates.TemplateResponse(
            request=request,
            name="partials/taxonomy_optimize_modal.html",
            context={
                "result": optimization_result,
                "taxonomy_json": taxonomy_json,
                "article_lookup": article_lookup,
                "article_count": len(articles),
                "loading": False,
            },
        )

    except Exception as e:
        logger.error(f"Taxonomy optimization failed: {e}")
        return templates.TemplateResponse(
            request=request,
            name="partials/taxonomy_optimize_modal.html",
            context={
                "error": f"Analysis failed: {str(e)}",
            },
        )


@router.post("/taxonomy/apply", response_class=HTMLResponse)
async def taxonomy_apply(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Apply the proposed taxonomy changes."""
    form = await request.form()
    taxonomy_json = form.get("taxonomy", "[]")

    try:
        taxonomy_data = json.loads(taxonomy_json)
    except json.JSONDecodeError:
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": "Invalid taxonomy data",
            },
        )

    try:
        # Step 1: Delete ALL existing article-category associations for this user's articles
        user_article_ids = await db.execute(
            select(Article.id).where(Article.user_id == current_user.id)
        )
        article_id_list = [row[0] for row in user_article_ids.all()]

        if article_id_list:
            await db.execute(
                delete(ArticleCategory).where(ArticleCategory.article_id.in_(article_id_list))
            )

        # Step 2: Delete ALL existing categories for this user (children first, then parents)
        # First delete subcategories (those with parent_id)
        await db.execute(
            delete(Category).where(
                Category.user_id == current_user.id,
                Category.parent_id.is_not(None),
            )
        )
        # Then delete parent categories
        await db.execute(
            delete(Category).where(
                Category.user_id == current_user.id,
            )
        )
        await db.flush()

        # Step 3: Create the new taxonomy structure
        articles_updated = 0
        categories_created = 0
        subcategories_created = 0

        for cat_data in taxonomy_data:
            category_name = cat_data.get("category", "")

            # Find or create the top-level category
            cat_result = await db.execute(
                select(Category).where(
                    Category.user_id == current_user.id,
                    Category.name == category_name,
                    Category.parent_id.is_(None),
                )
            )
            category = cat_result.scalar_one_or_none()

            if not category:
                category = Category(
                    user_id=current_user.id,
                    name=category_name,
                    parent_id=None,
                )
                db.add(category)
                await db.flush()
                categories_created += 1

            # Process subcategories
            for sub_data in cat_data.get("subcategories", []):
                subcat_name = sub_data.get("name", "")
                article_ids = sub_data.get("article_ids", [])

                # Find or create subcategory
                subcat_result = await db.execute(
                    select(Category).where(
                        Category.user_id == current_user.id,
                        Category.name == subcat_name,
                        Category.parent_id == category.id,
                    )
                )
                subcategory = subcat_result.scalar_one_or_none()

                if not subcategory:
                    subcategory = Category(
                        user_id=current_user.id,
                        name=subcat_name,
                        parent_id=category.id,
                    )
                    db.add(subcategory)
                    await db.flush()
                    subcategories_created += 1

                # Assign articles to this subcategory
                for article_id in article_ids:
                    try:
                        aid = UUID(article_id)

                        # Create new assignment (old ones already deleted above)
                        ac = ArticleCategory(
                            article_id=aid,
                            category_id=subcategory.id,
                            is_primary=True,
                            suggested_by_ai=True,
                        )
                        db.add(ac)
                        articles_updated += 1
                    except (ValueError, Exception) as e:
                        logger.warning(f"Failed to assign article {article_id}: {e}")
                        continue

        await db.commit()

        # Build success message
        message_parts = []
        if categories_created > 0:
            message_parts.append(f"{categories_created} new categories")
        if subcategories_created > 0:
            message_parts.append(f"{subcategories_created} new subcategories")
        message_parts.append(f"{articles_updated} articles reorganized")

        response = templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "success",
                "toast_message": "Taxonomy updated: " + ", ".join(message_parts),
            },
        )
        response.headers["HX-Trigger"] = "taxonomyApplied, sidebarRefresh"
        return response

    except Exception as e:
        logger.error(f"Failed to apply taxonomy: {e}")
        await db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="components/toast.html",
            context={
                "toast_type": "error",
                "toast_message": f"Failed to apply changes: {str(e)}",
            },
        )
