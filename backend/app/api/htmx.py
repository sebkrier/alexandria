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
