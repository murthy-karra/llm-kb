from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.wiki import Wiki


class WikiArticle(Base):
    __tablename__ = "wiki_articles"
    __table_args__ = (
        Index("idx_wiki_articles_wiki_id", "wiki_id"),
        Index("idx_wiki_articles_wiki_category", "wiki_id", "category"),
        Index("idx_wiki_articles_wiki_slug", "wiki_id", "slug", unique=True),
        {"schema": "app"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wiki_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("app.wikis.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False, default="general")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[dict | list] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[dict | list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    wiki: Mapped["Wiki"] = relationship(back_populates="articles")
