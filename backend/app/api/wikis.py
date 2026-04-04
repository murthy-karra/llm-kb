from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.wiki import Wiki
from app.models.wiki_file import WikiFile

router = APIRouter()


class CreateWikiRequest(BaseModel):
    name: str
    description: str = ""


class UpdateWikiRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class WikiResponse(BaseModel):
    id: str
    name: str
    description: str
    file_count: int
    total_size_bytes: int
    created_by: str
    created_at: datetime


@router.post("", response_model=WikiResponse)
async def create_wiki(
    req: CreateWikiRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can create wikis")

    if len(req.name) > 100:
        raise HTTPException(400, "Name must be 100 characters or less")

    wiki = Wiki(
        name=req.name,
        description=req.description,
        created_by=current_user.id,
    )
    db.add(wiki)
    await db.commit()
    await db.refresh(wiki)

    return WikiResponse(
        id=wiki.id,
        name=wiki.name,
        description=wiki.description,
        file_count=0,
        total_size_bytes=0,
        created_by=wiki.created_by,
        created_at=wiki.created_at,
    )


@router.get("", response_model=list[WikiResponse])
async def list_wikis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki))
    wikis = result.scalars().all()

    responses = []
    for wiki in wikis:
        file_count_result = await db.execute(
            select(func.count(WikiFile.id)).where(
                WikiFile.wiki_id == wiki.id, WikiFile.status == "clean"
            )
        )
        file_count = file_count_result.scalar() or 0

        total_size_result = await db.execute(
            select(func.sum(WikiFile.size_bytes)).where(
                WikiFile.wiki_id == wiki.id, WikiFile.status == "clean"
            )
        )
        total_size = total_size_result.scalar() or 0

        responses.append(
            WikiResponse(
                id=wiki.id,
                name=wiki.name,
                description=wiki.description,
                file_count=file_count,
                total_size_bytes=total_size,
                created_by=wiki.created_by,
                created_at=wiki.created_at,
            )
        )

    return responses


@router.get("/{wiki_id}", response_model=WikiResponse)
async def get_wiki(
    wiki_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    file_count_result = await db.execute(
        select(func.count(WikiFile.id)).where(
            WikiFile.wiki_id == wiki.id, WikiFile.status == "clean"
        )
    )
    file_count = file_count_result.scalar() or 0

    total_size_result = await db.execute(
        select(func.sum(WikiFile.size_bytes)).where(
            WikiFile.wiki_id == wiki.id, WikiFile.status == "clean"
        )
    )
    total_size = total_size_result.scalar() or 0

    return WikiResponse(
        id=wiki.id,
        name=wiki.name,
        description=wiki.description,
        file_count=file_count,
        total_size_bytes=total_size,
        created_by=wiki.created_by,
        created_at=wiki.created_at,
    )


@router.put("/{wiki_id}", response_model=WikiResponse)
async def update_wiki(
    wiki_id: str,
    req: UpdateWikiRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can update wikis")

    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    if req.name is not None:
        if len(req.name) > 100:
            raise HTTPException(400, "Name must be 100 characters or less")
        wiki.name = req.name
    if req.description is not None:
        wiki.description = req.description

    await db.commit()
    await db.refresh(wiki)

    file_count_result = await db.execute(
        select(func.count(WikiFile.id)).where(
            WikiFile.wiki_id == wiki.id, WikiFile.status == "clean"
        )
    )
    file_count = file_count_result.scalar() or 0

    total_size_result = await db.execute(
        select(func.sum(WikiFile.size_bytes)).where(
            WikiFile.wiki_id == wiki.id, WikiFile.status == "clean"
        )
    )
    total_size = total_size_result.scalar() or 0

    return WikiResponse(
        id=wiki.id,
        name=wiki.name,
        description=wiki.description,
        file_count=file_count,
        total_size_bytes=total_size,
        created_by=wiki.created_by,
        created_at=wiki.created_at,
    )


@router.delete("/{wiki_id}")
async def delete_wiki(
    wiki_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can delete wikis")

    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    await db.delete(wiki)
    await db.commit()

    return {"ok": True}
