from __future__ import annotations

import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from chatkit.server import NonStreamingResult, StreamingResult
from chatkit.store import NotFoundError

from .config import settings
from .instrumentation import configure_langfuse_tracing
from .server import NexusChatServer
from .stores import (
    InMemoryAttachmentStore,
    InMemoryStore,
    PostgresAttachmentStore,
    PostgresStore,
)

def configure_logging() -> None:
    """Ensure INFO-level app logs are emitted even under Uvicorn's defaults."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(logging.INFO)
    else:  # pragma: no cover - depends on runtime environment
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)-7s [%(name)s] %(message)s",
        )

configure_logging()

load_dotenv()
configure_langfuse_tracing()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.database_url:
    data_store = PostgresStore(settings.database_url)
    attachment_store = PostgresAttachmentStore(
        data_store,
        upload_base_url=settings.public_base_url,
    )
else:
    data_store = InMemoryStore()
    attachment_store = InMemoryAttachmentStore(
        data_store, upload_base_url=settings.public_base_url
    )
server = NexusChatServer(
    data_store,
    attachment_store,
    instructions=settings.assistant_instructions,
    history_limit=settings.history_limit,
)


def build_request_context(request: Request) -> dict[str, Any]:
    """Extract lightweight context from the incoming request for downstream use."""
    return {
        "user_id": request.headers.get("x-user-id"),
        "client": request.client.host if request.client else None,
    }


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    result = await server.process(await request.body(), {})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")


@app.post("/attachments/{attachment_id}/upload")
async def upload_attachment(attachment_id: str, file: UploadFile = File(...)):
    try:
        content = await file.read()
        await attachment_store.store_file_bytes(attachment_id, content)
        await data_store.mark_attachment_uploaded(attachment_id)
    except NotFoundError as exc:  # pragma: no cover - simple guardrail
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": attachment_id, "size": len(content)}


@app.get("/attachments/{attachment_id}")
async def read_attachment(attachment_id: str):
    try:
        payload, attachment = await attachment_store.get_file_bytes(attachment_id)
    except NotFoundError as exc:  # pragma: no cover - simple guardrail
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=payload, media_type=attachment.mime_type)


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/chatkit/config")
async def chatkit_config():
    return settings.get_public_config()
