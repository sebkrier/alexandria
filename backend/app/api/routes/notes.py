from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.models.note import Note
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter()


class NoteCreate(BaseModel):
    content: str


class NoteUpdate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: UUID
    article_id: UUID
    content: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/articles/{article_id}/notes", response_model=list[NoteResponse])
async def get_article_notes(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all notes for an article"""
    # Verify article belongs to user
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    # Get notes
    result = await db.execute(
        select(Note).where(Note.article_id == article_id).order_by(Note.created_at.desc())
    )
    notes = result.scalars().all()

    return [
        NoteResponse(
            id=n.id,
            article_id=n.article_id,
            content=n.content,
            created_at=n.created_at.isoformat(),
            updated_at=n.updated_at.isoformat(),
        )
        for n in notes
    ]


@router.post(
    "/articles/{article_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED
)
async def create_note(
    article_id: UUID,
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new note for an article"""
    # Verify article belongs to user
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    note = Note(
        article_id=article_id,
        content=data.content,
    )

    db.add(note)
    await db.commit()
    await db.refresh(note)

    return NoteResponse(
        id=note.id,
        article_id=note.article_id,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a note"""
    # Get note and verify ownership through article
    result = await db.execute(
        select(Note)
        .join(Article)
        .where(
            Note.id == note_id,
            Article.user_id == current_user.id,
        )
    )
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    note.content = data.content
    await db.commit()
    await db.refresh(note)

    return NoteResponse(
        id=note.id,
        article_id=note.article_id,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note"""
    # Get note and verify ownership through article
    result = await db.execute(
        select(Note)
        .join(Article)
        .where(
            Note.id == note_id,
            Article.user_id == current_user.id,
        )
    )
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    await db.delete(note)
    await db.commit()
