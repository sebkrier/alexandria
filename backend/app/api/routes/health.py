import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Health check endpoint"""
    # Check database connection
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning(f"Health check database connection failed: {e}")
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
    }
