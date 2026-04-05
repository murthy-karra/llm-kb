import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from botocore.exceptions import ClientError

from app.core.auth import get_current_user
from app.core.aws import get_s3_client
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.wiki import Wiki
from app.models.wiki_file import WikiFile

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/markdown",
    "text/plain",
}

MAX_FILE_SIZE = 10 * 1024 * 1024
SCAN_TIMEOUT_SECONDS = 10 * 60
RECENT_WINDOW_SECONDS = 60

GUARDDUTY_SCAN_STATUS_TAG = "GuardDutyMalwareScanStatus"
GUARDDUTY_THREAT_STATUS_TAG = "THREATS_FOUND"


class PresignFileRequest(BaseModel):
    filename: str
    relative_path: str = ""
    size_bytes: int
    content_type: str


class PresignBatchRequest(BaseModel):
    files: list[PresignFileRequest]


class PresignedFileResponse(BaseModel):
    filename: str
    relative_path: str
    presigned_url: str | None = None
    presigned_fields: dict | None = None
    s3_key: str | None = None
    file_id: str | None = None
    rejected: bool = False
    reject_reason: str | None = None


class PresignBatchResponse(BaseModel):
    accepted: list[PresignedFileResponse]
    rejected: list[PresignedFileResponse]


class ConfirmUploadRequest(BaseModel):
    file_ids: list[str]


class FileStatusResponse(BaseModel):
    file_id: str
    filename: str
    relative_path: str
    status: str
    scanned_at: datetime | None


class UploadStatusResponse(BaseModel):
    files: list[FileStatusResponse]
    all_complete: bool


class WikiFileResponse(BaseModel):
    id: str
    filename: str
    relative_path: str
    s3_key: str
    content_type: str
    size_bytes: int
    status: str
    scan_started_at: datetime | None
    transferred_at: datetime | None
    uploaded_by: str | None
    created_at: datetime


def _validate_path_traversal(path: str) -> bool:
    """Return True if path contains traversal attempts."""
    return ".." in path or path.startswith("/") or path.startswith("\\") or ":" in path


def _validate_content_type(content_type: str) -> bool:
    """Return True if content type is in allowed list."""
    return content_type.lower() in ALLOWED_CONTENT_TYPES


@router.post("/{wiki_id}/uploads/presign", response_model=PresignBatchResponse)
async def presign_upload_urls(
    wiki_id: str,
    req: PresignBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    if current_user.role != "admin" and wiki.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    accepted = []
    rejected = []

    from app.core.aws import generate_presigned_upload_url

    for file_req in req.files:
        if not file_req.filename:
            rejected.append(
                PresignedFileResponse(
                    filename=file_req.filename,
                    relative_path=file_req.relative_path,
                    rejected=True,
                    reject_reason="Filename cannot be empty",
                )
            )
            continue

        if file_req.size_bytes > MAX_FILE_SIZE:
            rejected.append(
                PresignedFileResponse(
                    filename=file_req.filename,
                    relative_path=file_req.relative_path,
                    rejected=True,
                    reject_reason=f"File size exceeds {MAX_FILE_SIZE / (1024 * 1024):.0f}MB limit",
                )
            )
            continue

        if not _validate_content_type(file_req.content_type):
            rejected.append(
                PresignedFileResponse(
                    filename=file_req.filename,
                    relative_path=file_req.relative_path,
                    rejected=True,
                    reject_reason=f"Content type '{file_req.content_type}' not allowed",
                )
            )
            continue

        if _validate_path_traversal(file_req.relative_path) or _validate_path_traversal(
            file_req.filename
        ):
            rejected.append(
                PresignedFileResponse(
                    filename=file_req.filename,
                    relative_path=file_req.relative_path,
                    rejected=True,
                    reject_reason="Invalid path characters",
                )
            )
            continue

        relative_path = file_req.relative_path.strip("/")
        s3_key = (
            f"wikis/{wiki_id}/{relative_path}/{file_req.filename}"
            if relative_path
            else f"wikis/{wiki_id}/{file_req.filename}"
        )

        # Handle duplicate s3_key: allow re-upload if previous attempt failed
        existing = await db.execute(
            select(WikiFile).where(WikiFile.s3_key == s3_key)
        )
        existing_file = existing.scalar_one_or_none()
        if existing_file:
            if existing_file.status == "clean":
                rejected.append(
                    PresignedFileResponse(
                        filename=file_req.filename,
                        relative_path=file_req.relative_path,
                        rejected=True,
                        reject_reason="File already exists in this wiki",
                    )
                )
                continue
            else:
                await db.delete(existing_file)
                await db.flush()

        wiki_file = WikiFile(
            wiki_id=wiki_id,
            filename=file_req.filename,
            relative_path=file_req.relative_path,
            s3_key=s3_key,
            content_type=file_req.content_type,
            size_bytes=file_req.size_bytes,
            status="pending_scan",
            uploaded_by=current_user.id,
        )
        db.add(wiki_file)
        await db.flush()
        await db.refresh(wiki_file)

        presigned = await asyncio.to_thread(
            generate_presigned_upload_url,
            s3_key=s3_key,
            content_type=file_req.content_type,
            max_size_bytes=MAX_FILE_SIZE,
            expires_in=900,
        )

        accepted.append(
            PresignedFileResponse(
                filename=file_req.filename,
                relative_path=file_req.relative_path,
                presigned_url=presigned["url"],
                presigned_fields=presigned["fields"],
                s3_key=s3_key,
                file_id=wiki_file.id,
                rejected=False,
            )
        )

    await db.commit()

    return PresignBatchResponse(accepted=accepted, rejected=rejected)


@router.post("/{wiki_id}/uploads/confirm")
async def confirm_upload(
    wiki_id: str,
    req: ConfirmUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    if current_user.role != "admin" and wiki.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    s3 = get_s3_client()

    for file_id in req.file_ids:
        result = await db.execute(
            select(WikiFile).where(WikiFile.id == file_id, WikiFile.wiki_id == wiki_id)
        )
        wiki_file = result.scalar_one_or_none()

        if not wiki_file:
            continue

        try:
            await asyncio.to_thread(
                s3.head_object,
                Bucket=settings.s3_quarantine_bucket,
                Key=wiki_file.s3_key,
            )
            wiki_file.scan_started_at = datetime.now(timezone.utc)
        except ClientError:
            wiki_file.status = "failed_upload"

    await db.commit()

    return {"ok": True}


@router.get("/{wiki_id}/uploads/status", response_model=UploadStatusResponse)
async def get_scan_status(
    wiki_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    if current_user.role != "admin" and wiki.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    now = datetime.now(timezone.utc)
    recent_threshold = now - timedelta(seconds=RECENT_WINDOW_SECONDS)

    # Read-only: scan processing is handled by background worker
    status_result = await db.execute(
        select(WikiFile).where(
            WikiFile.wiki_id == wiki_id,
            or_(
                # All still-pending files
                WikiFile.status == "pending_scan",
                # Recently completed files (within 60s window)
                and_(
                    WikiFile.status.in_(
                        ["clean", "failed_scan", "failed_timeout", "failed_upload"]
                    ),
                    or_(
                        WikiFile.transferred_at >= recent_threshold,
                        WikiFile.scan_started_at >= recent_threshold,
                    ),
                ),
            ),
        )
    )
    status_files = status_result.scalars().all()

    # all_complete checks ALL pending_scan files for this wiki, not just the filtered set
    pending_count_result = await db.execute(
        select(WikiFile).where(
            WikiFile.wiki_id == wiki_id,
            WikiFile.status == "pending_scan",
        )
    )
    any_pending = bool(pending_count_result.scalars().first())

    files_response = [
        FileStatusResponse(
            file_id=file.id,
            filename=file.filename,
            relative_path=file.relative_path,
            status=file.status,
            scanned_at=file.transferred_at
            if file.status == "clean"
            else file.scan_started_at,
        )
        for file in status_files
    ]

    return UploadStatusResponse(files=files_response, all_complete=not any_pending)


@router.get("/{wiki_id}/files", response_model=list[WikiFileResponse])
async def list_wiki_files(
    wiki_id: str,
    include_pending: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Wiki).where(Wiki.id == wiki_id))
    wiki = result.scalar_one_or_none()

    if not wiki:
        raise HTTPException(404, "Wiki not found")

    if current_user.role != "admin" and wiki.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    if include_pending:
        query = select(WikiFile).where(WikiFile.wiki_id == wiki_id)
    else:
        query = select(WikiFile).where(
            WikiFile.wiki_id == wiki_id,
            WikiFile.status == "clean",
        )

    result = await db.execute(query.order_by(WikiFile.relative_path, WikiFile.filename))
    files = result.scalars().all()

    return [
        WikiFileResponse(
            id=file.id,
            filename=file.filename,
            relative_path=file.relative_path,
            s3_key=file.s3_key,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            status=file.status,
            scan_started_at=file.scan_started_at,
            transferred_at=file.transferred_at,
            uploaded_by=file.uploaded_by,
            created_at=file.created_at,
        )
        for file in files
    ]
