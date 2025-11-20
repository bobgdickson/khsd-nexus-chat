from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

import json
import sqlalchemy as sa
from pydantic import TypeAdapter
from sqlalchemy.orm import Session, sessionmaker

from chatkit.store import AttachmentStore, NotFoundError, Store
from chatkit.types import (
    Attachment,
    AttachmentCreateParams,
    FileAttachment,
    ImageAttachment,
    Page,
    ThreadItem,
    ThreadMetadata,
)

from .models import AttachmentRow, ThreadItemRow, ThreadRow

T = TypeVar("T")

_thread_item_adapter = TypeAdapter(ThreadItem)
_attachment_adapter = TypeAdapter(Attachment)


def _serialize_model(model: Any) -> dict[str, Any]:
    return json.loads(model.model_dump_json())


def _deserialize_thread_item(payload: dict[str, Any]) -> ThreadItem:
    return _thread_item_adapter.validate_python(payload)


def _deserialize_attachment(payload: dict[str, Any]) -> Attachment:
    return _attachment_adapter.validate_python(payload)


class InMemoryStore(Store[dict[str, Any]]):
    """Simple in-memory implementation of the ChatKit persistence layer."""

    def __init__(self) -> None:
        self._threads: dict[str, ThreadMetadata] = {}
        self._items: dict[str, dict[str, ThreadItem]] = {}
        self._attachments: dict[str, Attachment] = {}
        self._lock = asyncio.Lock()

    async def load_thread(self, thread_id: str, context: dict[str, Any]) -> ThreadMetadata:
        async with self._lock:
            thread = self._threads.get(thread_id)
            if not thread:
                raise NotFoundError(f"Thread {thread_id} not found")
            return deepcopy(thread)

    async def save_thread(self, thread: ThreadMetadata, context: dict[str, Any]) -> None:
        async with self._lock:
            self._threads[thread.id] = deepcopy(thread)
            self._items.setdefault(thread.id, {})

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadItem]:
        async with self._lock:
            thread_items = list(self._items.get(thread_id, {}).values())

        reverse = order == "desc"
        thread_items.sort(key=lambda item: item.created_at, reverse=reverse)

        start_index = 0
        if after:
            for idx, item in enumerate(thread_items):
                if item.id == after:
                    start_index = idx + 1
                    break

        sliced = thread_items[start_index : start_index + limit]
        has_more = start_index + limit < len(thread_items)
        next_after = sliced[-1].id if has_more and sliced else None

        return Page(
            data=[deepcopy(item) for item in sliced],
            has_more=has_more,
            after=next_after,
        )

    async def save_attachment(self, attachment: Attachment, context: dict[str, Any]) -> None:
        async with self._lock:
            self._attachments[attachment.id] = deepcopy(attachment)

    async def load_attachment(self, attachment_id: str, context: dict[str, Any]) -> Attachment:
        async with self._lock:
            attachment = self._attachments.get(attachment_id)
            if not attachment:
                raise NotFoundError(f"Attachment {attachment_id} not found")
            return deepcopy(attachment)

    async def delete_attachment(self, attachment_id: str, context: dict[str, Any]) -> None:
        async with self._lock:
            self._attachments.pop(attachment_id, None)

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadMetadata]:
        async with self._lock:
            threads = list(self._threads.values())

        reverse = order == "desc"
        threads.sort(key=lambda thread: thread.created_at, reverse=reverse)

        start_index = 0
        if after:
            for idx, thread in enumerate(threads):
                if thread.id == after:
                    start_index = idx + 1
                    break

        sliced = threads[start_index : start_index + limit]
        has_more = start_index + limit < len(threads)
        next_after = sliced[-1].id if has_more and sliced else None

        return Page(
            data=[deepcopy(thread) for thread in sliced],
            has_more=has_more,
            after=next_after,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        async with self._lock:
            if thread_id not in self._threads:
                raise NotFoundError(f"Thread {thread_id} not found")
            self._items.setdefault(thread_id, {})[item.id] = deepcopy(item)

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        async with self._lock:
            if thread_id not in self._threads:
                raise NotFoundError(f"Thread {thread_id} not found")
            if item.id not in self._items.get(thread_id, {}):
                raise NotFoundError(f"Thread item {item.id} not found in thread {thread_id}")
            self._items[thread_id][item.id] = deepcopy(item)

    async def load_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> ThreadItem:
        async with self._lock:
            if thread_id not in self._threads:
                raise NotFoundError(f"Thread {thread_id} not found")
            item = self._items.get(thread_id, {}).get(item_id)
            if not item:
                raise NotFoundError(f"Thread item {item_id} not found in thread {thread_id}")
            return deepcopy(item)

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        async with self._lock:
            self._threads.pop(thread_id, None)
            self._items.pop(thread_id, None)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> None:
        async with self._lock:
            thread_items = self._items.get(thread_id, {})
            thread_items.pop(item_id, None)

    async def mark_attachment_uploaded(
        self, attachment_id: str, context: dict[str, Any] | None = None
    ) -> None:
        """Clear the upload_url once bytes have been stored."""
        context = context or {}
        async with self._lock:
            attachment = self._attachments.get(attachment_id)
            if not attachment:
                raise NotFoundError(f"Attachment {attachment_id} not found")
            if hasattr(attachment, "upload_url"):
                attachment.upload_url = None
            self._attachments[attachment_id] = deepcopy(attachment)


class InMemoryAttachmentStore(AttachmentStore[dict[str, Any]]):
    """Handles attachment registration and byte storage in memory."""

    def __init__(self, data_store: InMemoryStore, upload_base_url: str) -> None:
        self._files: dict[str, bytes] = {}
        self._lock = asyncio.Lock()
        self._data_store = data_store
        self._upload_base_url = upload_base_url.rstrip("/")

    async def create_attachment(
        self, input: AttachmentCreateParams, context: dict[str, Any]
    ) -> Attachment:
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = f"{self._upload_base_url}/attachments/{attachment_id}/upload"
        attachment: Attachment
        if input.mime_type.startswith("image/"):
            attachment = ImageAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=upload_url,
            )
        else:
            attachment = FileAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=upload_url,
            )

        async with self._lock:
            self._files[attachment_id] = b""
        await self._data_store.save_attachment(attachment, context)
        return attachment

    async def delete_attachment(self, attachment_id: str, context: dict[str, Any]) -> None:
        async with self._lock:
            self._files.pop(attachment_id, None)

    async def store_file_bytes(
        self, attachment_id: str, payload: bytes, context: dict[str, Any] | None = None
    ) -> Attachment:
        async with self._lock:
            if attachment_id not in self._files:
                raise NotFoundError(f"Attachment {attachment_id} not found")
            self._files[attachment_id] = payload
        return await self._data_store.load_attachment(attachment_id, context=context or {})

    async def get_file_bytes(
        self, attachment_id: str, context: dict[str, Any] | None = None
    ) -> tuple[bytes, Attachment]:
        async with self._lock:
            if attachment_id not in self._files:
                raise NotFoundError(f"Attachment {attachment_id} not found")
        payload = self._files[attachment_id]
        attachment = await self._data_store.load_attachment(attachment_id, context=context or {})
        return payload, attachment


class PostgresStore(Store[dict[str, Any]]):
    """PostgreSQL-backed implementation of the ChatKit persistence layer."""

    def __init__(self, database_url: str) -> None:
        self.engine = sa.create_engine(database_url, future=True)
        self._Session = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False)

    @property
    def session_factory(self) -> sessionmaker[Session]:
        return self._Session

    async def _run(self, fn: Callable[[Session], T]) -> T:
        return await asyncio.to_thread(self._run_sync, fn)

    def _run_sync(self, fn: Callable[[Session], T]) -> T:
        with self._Session() as session:
            return fn(session)

    def _deser_thread(self, row: ThreadRow) -> ThreadMetadata:
        return ThreadMetadata.model_validate(row.data)

    async def load_thread(self, thread_id: str, context: dict[str, Any]) -> ThreadMetadata:
        def op(session: Session) -> ThreadMetadata:
            row = session.get(ThreadRow, thread_id)
            if not row:
                raise NotFoundError(f"Thread {thread_id} not found")
            return self._deser_thread(row)

        return await self._run(op)

    async def save_thread(self, thread: ThreadMetadata, context: dict[str, Any]) -> None:
        data = _serialize_model(thread)
        created_at = thread.created_at or datetime.now(timezone.utc)

        def op(session: Session) -> None:
            row = session.get(ThreadRow, thread.id)
            if row:
                row.data = data
                row.created_at = created_at
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(
                    ThreadRow(
                        id=thread.id,
                        data=data,
                        created_at=created_at,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()

        await self._run(op)

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadItem]:
        def op(session: Session) -> Page[ThreadItem]:
            query = session.query(ThreadItemRow).filter(ThreadItemRow.thread_id == thread_id)
            if after:
                anchor = session.get(ThreadItemRow, after)
                if not anchor:
                    raise NotFoundError(f"Thread item {after} not found")
                comparator = sa.tuple_(ThreadItemRow.created_at, ThreadItemRow.id)
                anchor_key = (anchor.created_at, anchor.id)
                if order == "desc":
                    query = query.filter(comparator < anchor_key)
                else:
                    query = query.filter(comparator > anchor_key)

            sort_columns = [
                ThreadItemRow.created_at.desc() if order == "desc" else ThreadItemRow.created_at.asc(),
                ThreadItemRow.id.asc(),
            ]
            rows = query.order_by(*sort_columns).limit(limit + 1).all()
            has_more = len(rows) > limit
            rows = rows[:limit]
            next_after = rows[-1].id if has_more and rows else None
            items = [_deserialize_thread_item(row.data) for row in rows]
            return Page(data=items, has_more=has_more, after=next_after)

        return await self._run(op)

    async def save_attachment(self, attachment: Attachment, context: dict[str, Any]) -> None:
        data = _serialize_model(attachment)
        upload_url = data.get("upload_url")

        def op(session: Session) -> None:
            row = session.get(AttachmentRow, attachment.id)
            if row:
                row.data = data
                row.mime_type = attachment.mime_type
                row.upload_url = upload_url
            else:
                session.add(
                    AttachmentRow(
                        id=attachment.id,
                        data=data,
                        mime_type=attachment.mime_type,
                        upload_url=upload_url,
                        created_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()

        await self._run(op)

    async def load_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> Attachment:
        def op(session: Session) -> Attachment:
            row = session.get(AttachmentRow, attachment_id)
            if not row:
                raise NotFoundError(f"Attachment {attachment_id} not found")
            return _deserialize_attachment(row.data)

        return await self._run(op)

    async def delete_attachment(self, attachment_id: str, context: dict[str, Any]) -> None:
        def op(session: Session) -> None:
            row = session.get(AttachmentRow, attachment_id)
            if row:
                session.delete(row)
                session.commit()

        await self._run(op)

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadMetadata]:
        def op(session: Session) -> Page[ThreadMetadata]:
            query = session.query(ThreadRow)
            if after:
                anchor = session.get(ThreadRow, after)
                if not anchor:
                    raise NotFoundError(f"Thread {after} not found")
                comparator = sa.tuple_(ThreadRow.created_at, ThreadRow.id)
                anchor_key = (anchor.created_at, anchor.id)
                if order == "desc":
                    query = query.filter(comparator < anchor_key)
                else:
                    query = query.filter(comparator > anchor_key)

            sort_columns = [
                ThreadRow.created_at.desc() if order == "desc" else ThreadRow.created_at.asc(),
                ThreadRow.id.asc(),
            ]
            rows = query.order_by(*sort_columns).limit(limit + 1).all()
            has_more = len(rows) > limit
            rows = rows[:limit]
            next_after = rows[-1].id if has_more and rows else None
            threads = [self._deser_thread(row) for row in rows]
            return Page(data=threads, has_more=has_more, after=next_after)

        return await self._run(op)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        data = _serialize_model(item)
        created_at = getattr(item, "created_at", None) or datetime.now(timezone.utc)

        def op(session: Session) -> None:
            thread_exists = session.get(ThreadRow, thread_id)
            if not thread_exists:
                raise NotFoundError(f"Thread {thread_id} not found")
            session.add(
                ThreadItemRow(
                    id=item.id,
                    thread_id=thread_id,
                    data=data,
                    created_at=created_at,
                )
            )
            session.commit()

        await self._run(op)

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        data = _serialize_model(item)

        def op(session: Session) -> None:
            row = session.get(ThreadItemRow, item.id)
            if not row:
                raise NotFoundError(f"Thread item {item.id} not found in thread {thread_id}")
            row.data = data
            row.thread_id = thread_id
            session.commit()

        await self._run(op)

    async def load_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> ThreadItem:
        def op(session: Session) -> ThreadItem:
            row = session.get(ThreadItemRow, item_id)
            if not row or row.thread_id != thread_id:
                raise NotFoundError(f"Thread item {item_id} not found in thread {thread_id}")
            return _deserialize_thread_item(row.data)

        return await self._run(op)

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        def op(session: Session) -> None:
            row = session.get(ThreadRow, thread_id)
            if row:
                session.delete(row)
                session.commit()

        await self._run(op)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> None:
        def op(session: Session) -> None:
            row = session.get(ThreadItemRow, item_id)
            if row and row.thread_id == thread_id:
                session.delete(row)
                session.commit()

        await self._run(op)

    async def mark_attachment_uploaded(
        self, attachment_id: str, context: dict[str, Any] | None = None
    ) -> None:
        def op(session: Session) -> None:
            row = session.get(AttachmentRow, attachment_id)
            if not row:
                raise NotFoundError(f"Attachment {attachment_id} not found")
            data = row.data.copy()
            data["upload_url"] = None
            row.data = data
            row.upload_url = None
            session.commit()

        await self._run(op)


class PostgresAttachmentStore(AttachmentStore[dict[str, Any]]):
    """Attachment store that persists bytes in PostgreSQL."""

    def __init__(self, store: PostgresStore, upload_base_url: str) -> None:
        self.store = store
        self._Session = store.session_factory
        self._upload_base_url = upload_base_url.rstrip("/")

    async def _run(self, fn: Callable[[Session], T]) -> T:
        return await asyncio.to_thread(self._run_sync, fn)

    def _run_sync(self, fn: Callable[[Session], T]) -> T:
        with self._Session() as session:
            return fn(session)

    async def create_attachment(
        self, input: AttachmentCreateParams, context: dict[str, Any]
    ) -> Attachment:
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = f"{self._upload_base_url}/attachments/{attachment_id}/upload"
        if input.mime_type.startswith("image/"):
            attachment: Attachment = ImageAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=upload_url,
            )
        else:
            attachment = FileAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=upload_url,
            )
        await self.store.save_attachment(attachment, context)
        return attachment

    async def delete_attachment(self, attachment_id: str, context: dict[str, Any]) -> None:
        def op(session: Session) -> None:
            row = session.get(AttachmentRow, attachment_id)
            if row:
                row.file_bytes = None
                session.commit()

        await self._run(op)

    async def store_file_bytes(
        self, attachment_id: str, payload: bytes, context: dict[str, Any] | None = None
    ) -> Attachment:
        def op(session: Session) -> Attachment:
            row = session.get(AttachmentRow, attachment_id)
            if not row:
                raise NotFoundError(f"Attachment {attachment_id} not found")
            row.file_bytes = payload
            session.commit()
            return _deserialize_attachment(row.data)

        return await self._run(op)

    async def get_file_bytes(
        self, attachment_id: str, context: dict[str, Any] | None = None
    ) -> tuple[bytes, Attachment]:
        def op(session: Session) -> tuple[bytes, Attachment]:
            row = session.get(AttachmentRow, attachment_id)
            if not row or row.file_bytes is None:
                raise NotFoundError(f"Attachment {attachment_id} has no stored bytes")
            return row.file_bytes, _deserialize_attachment(row.data)

        return await self._run(op)
