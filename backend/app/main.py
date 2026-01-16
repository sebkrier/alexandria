import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import api_router
from app.api.htmx import router as htmx_router
from app.config import get_settings
from app.db.raw import close_pool, init_pool

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Alexandria API")
    await init_pool()
    yield
    # Shutdown
    logger.info("Shutting down Alexandria API")
    await close_pool()


app = FastAPI(
    title="Alexandria",
    description="Personal Research Library API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Include HTMX routes (HTML pages)
app.include_router(htmx_router, prefix="/app")


@app.get("/")
async def root():
    return {
        "name": "Alexandria",
        "description": "Personal Research Library",
        "version": "0.1.0",
        "docs": "/docs",
    }
