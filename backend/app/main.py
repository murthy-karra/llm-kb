from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
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
from app.core.database import async_session, get_db, init_db
from app.models.user import User
from app.api.wikis import router as wikis_router
from app.api.uploads import router as uploads_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as db:
        await seed_users(db)
    yield


app = FastAPI(title="LLM Knowledge Base", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wikis_router, prefix="/api/wikis", tags=["wikis"])
app.include_router(uploads_router, prefix="/api/wikis", tags=["uploads"])


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
async def login(
    req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    set_refresh_cookie(response, refresh_token)
    return {
        "token": access_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
        },
    }


@app.post("/api/auth/register")
async def register(
    req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
):
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
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
        },
    }


@app.post("/api/auth/refresh")
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
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
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
        },
    }


@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_refresh_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
    }
