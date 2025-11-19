from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime
from typing import Any

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

    def __init__(self, data_store: InMemoryStore) -> None:
        self._files: dict[str, bytes] = {}
        self._lock = asyncio.Lock()
        self._data_store = data_store

    async def create_attachment(
        self, input: AttachmentCreateParams, context: dict[str, Any]
    ) -> Attachment:
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = f"/attachments/{attachment_id}/upload"
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
