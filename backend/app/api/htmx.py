"""
HTMX Routes - HTML pages served by FastAPI with Jinja2 templates.

These routes return HTML instead of JSON, and are used by the HTMX frontend.
The JSON API routes in /api/* remain unchanged for backwards compatibility.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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


# Mock article data for testing
MOCK_ARTICLES = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "title": "Understanding Large Language Models: A Comprehensive Guide",
        "source_type": "url",
        "media_type": "article",
        "original_url": "https://example.com/llm-guide",
        "summary": """Large language models (LLMs) have revolutionized natural language processing.

This guide explores the architecture, training methods, and applications of modern LLMs like GPT-4 and Claude.

## Key Concepts
- Transformer architecture
- Attention mechanisms
- Fine-tuning strategies""",
        "is_read": False,
        "reading_time_minutes": 12,
        "processing_status": "completed",
        "color": {"hex_value": "#6B7FD7"},  # Blue
        "categories": [{"id": "cat1", "name": "AI/ML"}],
        "tags": [
            {"id": "tag1", "name": "LLM", "color": "#8B5CF6"},
            {"id": "tag2", "name": "Research", "color": "#10B981"},
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "title": "Attention Is All You Need - The Paper That Changed NLP",
        "source_type": "arxiv",
        "media_type": "paper",
        "original_url": "https://arxiv.org/abs/1706.03762",
        "summary": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism.",
        "is_read": True,
        "reading_time_minutes": 45,
        "processing_status": "completed",
        "color": None,
        "categories": [{"id": "cat2", "name": "Papers"}],
        "tags": [
            {"id": "tag3", "name": "Transformers", "color": "#F59E0B"},
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "title": "Building Production ML Systems - Stanford CS229",
        "source_type": "video",
        "media_type": "video",
        "original_url": "https://youtube.com/watch?v=example",
        "summary": "Learn how to build and deploy machine learning systems in production environments.",
        "is_read": False,
        "reading_time_minutes": 90,
        "processing_status": "processing",
        "color": {"hex_value": "#D4915D"},  # Orange
        "categories": [],
        "tags": [
            {"id": "tag4", "name": "MLOps", "color": "#EC4899"},
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "title": "The State of AI in 2024",
        "source_type": "pdf",
        "media_type": "pdf",
        "original_url": None,
        "summary": None,
        "is_read": False,
        "reading_time_minutes": None,
        "processing_status": "pending",
        "color": {"hex_value": "#D46A6A"},  # Red
        "categories": [{"id": "cat3", "name": "Reports"}],
        "tags": [],
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
