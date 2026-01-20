from fastapi import APIRouter

from . import articles, ask, general, reader, remote, settings

router = APIRouter()

router.include_router(general.router)
router.include_router(articles.router)
router.include_router(settings.router)
router.include_router(reader.router)
router.include_router(remote.router)
router.include_router(ask.router)
