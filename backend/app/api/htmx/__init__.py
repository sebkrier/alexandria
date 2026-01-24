"""
HTMX Routes Package - HTML pages served by FastAPI with Jinja2 templates.

This package contains all HTMX routes split into feature modules:
- main: Core article routes (index, article detail, etc.)
- settings: AI providers and color management
- (more modules will be added as refactoring continues)

The main router combines all sub-routers for backwards compatibility.
"""

from fastapi import APIRouter

# Import routers from sub-modules
from app.api.htmx.main import router as main_router
from app.api.htmx.settings import router as settings_router

# Create combined router that includes all sub-routers
router = APIRouter()

# Include all sub-routers (order matters for route matching)
router.include_router(settings_router)
router.include_router(main_router)
