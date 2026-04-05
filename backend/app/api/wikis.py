from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.wiki import Wiki
from app.models.wiki_article import WikiArticle
from app.models.wiki_file import WikiFile
from app.models.wiki_job import WikiJob

router = APIRouter()


class CreateWikiRequest(BaseModel):
    name: str
    description: str = ""


class UpdateWikiRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    compile_model: str | None = None
    polish_model: str | None = None
    qa_model: str | None = None


class WikiResponse(BaseModel):
    id: str
    name: str
    description: str
    compile_model: str
    polish_model: str
    qa_model: str
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
        compile_model=wiki.compile_model,
        polish_model=wiki.polish_model,
        qa_model=wiki.qa_model,
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
                compile_model=wiki.compile_model,
                polish_model=wiki.polish_model,
                qa_model=wiki.qa_model,
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
        compile_model=wiki.compile_model,
        polish_model=wiki.polish_model,
        qa_model=wiki.qa_model,
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
    if req.compile_model is not None:
        wiki.compile_model = req.compile_model
    if req.polish_model is not None:
        wiki.polish_model = req.polish_model
    if req.qa_model is not None:
        wiki.qa_model = req.qa_model

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
        compile_model=wiki.compile_model,
        polish_model=wiki.polish_model,
        qa_model=wiki.qa_model,
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


# ---------- Jobs: Compile & Lint ----------


class CompileWikiRequest(BaseModel):
    full: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: str
    job_type: str
    created_at: datetime


class JobDetailResponse(JobResponse):
    result: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@router.post("/{wiki_id}/compile", response_model=JobResponse)
async def compile_wiki(
    wiki_id: str,
    req: CompileWikiRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can compile wikis")

    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Wiki not found")

    # Check for already running compile/rebuild on this wiki
    running = await db.execute(
        select(WikiJob).where(
            WikiJob.wiki_id == wiki_id,
            WikiJob.job_type.in_(["compile", "full_rebuild"]),
            WikiJob.status.in_(["pending", "running"]),
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(409, "A compile job is already running for this wiki")

    job = WikiJob(
        wiki_id=wiki_id,
        job_type="full_rebuild" if req.full else "compile",
        status="pending",
        created_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return JobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        created_at=job.created_at,
    )


@router.post("/{wiki_id}/lint", response_model=JobResponse)
async def lint_wiki(
    wiki_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can lint wikis")

    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Wiki not found")

    running = await db.execute(
        select(WikiJob).where(
            WikiJob.wiki_id == wiki_id,
            WikiJob.job_type == "lint",
            WikiJob.status.in_(["pending", "running"]),
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(409, "A lint job is already running for this wiki")

    job = WikiJob(
        wiki_id=wiki_id,
        job_type="lint",
        status="pending",
        created_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return JobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        created_at=job.created_at,
    )


@router.get("/{wiki_id}/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_status(
    wiki_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WikiJob).where(WikiJob.id == job_id, WikiJob.wiki_id == wiki_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    return JobDetailResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        result=job.result,
        error=job.error,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.get("/{wiki_id}/jobs", response_model=list[JobDetailResponse])
async def list_jobs(
    wiki_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WikiJob)
        .where(WikiJob.wiki_id == wiki_id)
        .order_by(WikiJob.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()

    return [
        JobDetailResponse(
            job_id=j.id,
            status=j.status,
            job_type=j.job_type,
            result=j.result,
            error=j.error,
            started_at=j.started_at,
            completed_at=j.completed_at,
            created_at=j.created_at,
        )
        for j in jobs
    ]


# ---------- Articles ----------


class ArticleResponse(BaseModel):
    id: str
    slug: str
    title: str
    category: str
    preview: str
    sources: list
    tags: list
    created_at: datetime
    updated_at: datetime


class ArticleDetailResponse(ArticleResponse):
    content: str


@router.get("/{wiki_id}/articles", response_model=list[ArticleResponse])
async def list_articles(
    wiki_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Wiki not found")

    articles_result = await db.execute(
        select(WikiArticle)
        .where(WikiArticle.wiki_id == wiki_id)
        .order_by(WikiArticle.category, WikiArticle.title)
    )
    articles = articles_result.scalars().all()

    return [
        ArticleResponse(
            id=a.id,
            slug=a.slug,
            title=a.title,
            category=a.category,
            preview=a.content[:200].replace("\n", " "),
            sources=a.sources,
            tags=a.tags,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in articles
    ]


@router.get("/{wiki_id}/articles/{slug}", response_model=ArticleDetailResponse)
async def get_article(
    wiki_id: str,
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WikiArticle).where(
            WikiArticle.wiki_id == wiki_id,
            WikiArticle.slug == slug,
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    return ArticleDetailResponse(
        id=article.id,
        slug=article.slug,
        title=article.title,
        category=article.category,
        content=article.content,
        preview=article.content[:200].replace("\n", " "),
        sources=article.sources,
        tags=article.tags,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


# ---------- Q&A ----------


class AskWikiRequest(BaseModel):
    question: str


@router.post("/{wiki_id}/ask")
async def ask_wiki(
    wiki_id: str,
    req: AskWikiRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Wiki not found")

    from app.compilation.wiki_compiler import ask_wiki_scoped
    answer, resp = await ask_wiki_scoped(wiki_id, req.question, db)

    return {
        "question": req.question,
        "answer": answer,
        "usage": {
            "model": resp.model,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "cost_usd": round(resp.cost_usd, 4),
        },
    }


# ---------- Search (proxy to Rust Tantivy engine) ----------


class SearchWikiRequest(BaseModel):
    query: str
    limit: int = 10


@router.post("/{wiki_id}/search")
async def search_wiki(
    wiki_id: str,
    req: SearchWikiRequest,
    current_user: User = Depends(get_current_user),
):
    import httpx
    from app.core.config import settings
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.search_engine_url}/search/{wiki_id}",
                json={"query": req.query, "limit": req.limit},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Search engine unavailable: {e}")
