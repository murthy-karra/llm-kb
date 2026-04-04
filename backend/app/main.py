from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    clear_refresh_cookie,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    seed_users,
    set_refresh_cookie,
    verify_password,
)
from app.core.config import PROVIDER_PRESETS, apply_model_override, ensure_dirs, settings
from app.core.database import async_session, get_db, init_db
from app.core.filesystem import (
    get_wiki_index_content,
    list_raw_files,
    list_wiki_articles,
    read_file,
    read_with_frontmatter,
)
from app.models.user import User

ensure_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as db:
        await seed_users(db)
    yield


app = FastAPI(title="LLM Knowledge Base", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- helpers ----------

def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())


# ---------- Auth endpoints ----------

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str


@app.post("/api/auth/login")
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    set_refresh_cookie(response, refresh_token)
    return {
        "token": access_token,
        "user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "role": user.role},
    }


@app.post("/api/auth/register")
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")
    user = User(
        email=req.email,
        first_name=req.first_name,
        last_name=req.last_name,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    set_refresh_cookie(response, refresh_token)
    return {
        "token": access_token,
        "user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "role": user.role},
    }


@app.post("/api/auth/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "No refresh token")
    payload = decode_token(token, expected_type="refresh")
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    set_refresh_cookie(response, refresh_token)
    return {
        "token": access_token,
        "user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "role": user.role},
    }


@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_refresh_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "role": user.role}


# ---------- GET endpoints ----------

@app.get("/api/status")
def get_status():
    raw_files = list_raw_files()
    wiki_articles = list_wiki_articles()
    return {
        "raw_count": len(raw_files),
        "wiki_count": len(wiki_articles),
        "raw_size_kb": round(_dir_size(settings.raw_dir) / 1024, 1),
        "wiki_size_kb": round(_dir_size(settings.wiki_dir) / 1024, 1),
        "output_count": len(list(settings.output_dir.glob("*"))),
    }


@app.get("/api/wiki/index")
def get_wiki_index():
    return {"content": get_wiki_index_content()}


@app.get("/api/wiki/articles")
def get_wiki_articles():
    articles = []
    for path in list_wiki_articles():
        meta, content = read_with_frontmatter(path)
        rel = str(path.relative_to(settings.wiki_dir))
        preview = ""
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                preview = line[:200]
                break
        articles.append({
            "path": rel,
            "title": meta.get("title", path.stem),
            "category": meta.get("category", ""),
            "tags": meta.get("tags", []),
            "preview": preview,
        })
    return {"articles": articles}


@app.get("/api/wiki/article/{path:path}")
def get_wiki_article(path: str):
    full_path = settings.wiki_dir / path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "Article not found")
    meta, content = read_with_frontmatter(full_path)
    return {"metadata": meta, "content": content}


@app.get("/api/raw/files")
def get_raw_files():
    files = []
    for path in list_raw_files():
        files.append({
            "path": path.name,
            "size_kb": round(path.stat().st_size / 1024, 1),
        })
    return {"files": files}


@app.get("/api/raw/file/{path:path}")
def get_raw_file(path: str):
    full_path = settings.raw_dir / path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "File not found")
    return {"content": read_file(full_path)}


# ---------- Image endpoints ----------

@app.get("/api/image/{slug}")
def get_image(slug: str, style: str = "hero"):
    from app.core.images import get_cached_image
    path = get_cached_image(slug, style)
    if not path:
        raise HTTPException(404, "Image not generated yet")
    return FileResponse(path, media_type="image/png")


class GenerateImageRequest(BaseModel):
    slug: str
    title: str
    category: str
    preview: str = ""
    style: str = "hero"


@app.post("/api/image/generate")
def post_generate_image(req: GenerateImageRequest):
    from app.core.images import generate_article_image
    path = generate_article_image(
        article_slug=req.slug,
        title=req.title,
        category=req.category,
        preview=req.preview,
        style=req.style,
    )
    return {"slug": req.slug, "style": req.style, "path": str(path.name)}


# ---------- POST endpoints ----------

@app.get("/api/models")
def get_models():
    default = settings.llm_model
    presets = [
        {"id": key, "name": key.title(), "model": p["model"]}
        for key, p in PROVIDER_PRESETS.items()
    ]
    return {"default": default, "presets": presets}


class AskRequest(BaseModel):
    question: str
    model: str | None = None


@app.post("/api/ask")
def post_ask(req: AskRequest):
    from app.compilation.qa import ask_wiki

    apply_model_override(req.model)
    result = ask_wiki(req.question, save_output=True)
    return {
        "question": req.question,
        "answer": result.text,
        "model": result.model,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "cost_usd": result.cost_usd,
    }


class CompileRequest(BaseModel):
    full: bool = False


@app.post("/api/compile")
def post_compile(req: CompileRequest):
    from app.compilation.compiler import compile_wiki
    written = compile_wiki(full_rebuild=req.full)
    return {"articles_written": len(written), "paths": written}


@app.post("/api/lint")
def post_lint():
    from app.linting.linter import lint_wiki
    report = lint_wiki(fix=False)
    return {"report": report}


class IngestURLRequest(BaseModel):
    url: str


@app.post("/api/ingest/url")
def post_ingest_url(req: IngestURLRequest):
    from app.ingestion.ingest import ingest_url
    path = ingest_url(req.url)
    return {"path": str(path.name)}


@app.post("/api/ingest/upload")
async def post_ingest_upload(file: UploadFile):
    import tempfile

    from app.ingestion.ingest import ingest

    suffix = Path(file.filename).suffix if file.filename else ".md"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = ingest(tmp_path)
        if isinstance(result, list):
            return {"paths": [str(p.name) for p in result]}
        return {"path": str(result.name)}
    finally:
        Path(tmp_path).unlink(missing_ok=True)
