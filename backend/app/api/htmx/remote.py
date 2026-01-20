from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.auth import get_current_user

from .utils import fetch_sidebar_data, templates

router = APIRouter()

@router.get("/remote", response_class=HTMLResponse)
async def remote_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remote add page - WhatsApp bot setup instructions."""
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="pages/remote.html",
        context={
            "current_path": "/app/remote",
            **sidebar_data,
        },
    )
