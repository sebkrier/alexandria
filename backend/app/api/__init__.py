from fastapi import APIRouter

from app.api.routes import articles, categories, health, notes, settings, tags

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(articles.router, prefix="/articles", tags=["articles"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(notes.router, tags=["notes"])  # No prefix - routes define their own paths
