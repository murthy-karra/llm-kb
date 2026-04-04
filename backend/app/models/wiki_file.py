from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.wiki import Wiki


class WikiFile(Base):
    __tablename__ = "wiki_files"
    __table_args__ = (
        Index("idx_wiki_files_wiki_status", "wiki_id", "status"),
        {"schema": "app"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wiki_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("app.wikis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    s3_key: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending_scan", index=True
    )
    scan_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transferred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    wiki: Mapped["Wiki"] = relationship(back_populates="files")
