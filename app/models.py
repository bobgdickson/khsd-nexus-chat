from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ThreadRow(Base):
    __tablename__ = "chatkit_threads"

    id: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    items: Mapped[list["ThreadItemRow"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ThreadItemRow(Base):
    __tablename__ = "chatkit_thread_items"

    id: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        sa.ForeignKey("chatkit_threads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    data: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    thread: Mapped[ThreadRow] = relationship(back_populates="items")


class AttachmentRow(Base):
    __tablename__ = "chatkit_attachments"

    id: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    upload_url: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    file_bytes: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
