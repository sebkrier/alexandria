from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.article_service import ArticleService
from app.utils.auth import get_current_user

from .utils import article_to_dict, fetch_sidebar_data, fetch_unread_count, templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    search: str | None = None,
    view: str = "grid",
    page: int = Query(1, ge=1),
    page_size: int = Query(1000, ge=1, le=10000),  # Show all articles by default
    category_id: UUID | None = None,
    color_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Main article list page."""
    service = ArticleService(db)
    # Fetch articles using service
    articles, total = await service.list_articles(
        user_id=current_user.id,
        search=search,
        page=page,
        page_size=page_size,
        category_id=category_id,
        color_id=color_id,
    )

    total_pages = (total + page_size - 1) // page_size

    # Fetch sidebar data
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="pages/index.html",
        context={
            "articles": [article_to_dict(a) for a in articles],
            "view_mode": view,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "search": search,
            "current_path": str(request.url.path),
            "selected_category_id": str(category_id) if category_id else None,
            "selected_color_id": str(color_id) if color_id else None,
            "colors": sidebar_data.get("colors", []),  # For bulk action bar color picker
            **sidebar_data,
        },
    )

@router.get("/sidebar/unread-count", response_class=HTMLResponse)
async def sidebar_unread_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the sidebar unread count partial for HTMX updates."""
    # Count unread articles
    unread_count = await fetch_unread_count(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_unread_count.html",
        context={
            "unread_count": unread_count,
            "current_path": str(request.url.path),
        },
    )

# Test routes
@router.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """Test page to verify HTMX + Jinja2 setup is working."""
    return templates.TemplateResponse(
        request=request,
        name="pages/test.html",
        context={
            "title": "HTMX Test Page",
            "message": "If you can see this, HTMX + Jinja2 is working!",
            "features": [
                "Tailwind CSS via CDN",
                "HTMX for dynamic updates",
                "Alpine.js for client state",
                "Dark mode styling",
            ],
        },
    )


@router.get("/test/click", response_class=HTMLResponse)
async def test_click(request: Request):
    """Partial response for HTMX click test."""
    import random  # noqa: S311

    colors = [
        "text-article-blue",
        "text-article-green",
        "text-article-orange",
        "text-article-purple",
        "text-article-red",
    ]
    color = random.choice(colors)  # noqa: S311
    return f'<span class="{color} font-bold">Button clicked! HTMX is working.</span>'

MOCK_ARTICLES = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "title": "Understanding Large Language Models: A Comprehensive Guide",
        "source_type": "url",
        "media_type": "article",
        "original_url": "https://example.com/llm-guide",
        "summary": "Large language models (LLMs) have revolutionized natural language processing...",
        "is_read": False,
        "reading_time_minutes": 12,
        "processing_status": "completed",
        "color": {"hex_value": "#6B7FD7"},
        "categories": [{"id": "cat1", "name": "AI/ML"}],
        "tags": [
            {"id": "tag1", "name": "LLM", "color": "#8B5CF6"},
            {"id": "tag2", "name": "Research", "color": "#10B981"},
        ],
    },
]

@router.get("/test/card", response_class=HTMLResponse)
async def test_card(request: Request, view: str = "grid"):
    """Test page to preview article cards with mock data."""
    return templates.TemplateResponse(
        request=request,
        name="pages/test_cards.html",
        context={
            "title": "Article Card Test",
            "articles": MOCK_ARTICLES,
            "view_mode": view,
        },
    )
