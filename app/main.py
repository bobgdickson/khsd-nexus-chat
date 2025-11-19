from __future__ import annotations

import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from chatkit.server import NonStreamingResult, StreamingResult
from chatkit.store import NotFoundError

from .config import settings
from .server import NexusChatServer
from .stores import InMemoryAttachmentStore, InMemoryStore

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

data_store = InMemoryStore()
attachment_store = InMemoryAttachmentStore(data_store)
server = NexusChatServer(data_store, attachment_store)


def build_request_context(request: Request) -> dict[str, Any]:
    """Extract lightweight context from the incoming request for downstream use."""
    return {
        "user_id": request.headers.get("x-user-id"),
        "client": request.client.host if request.client else None,
    }


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    payload = await request.body()
    context = build_request_context(request)
    result = await server.process(payload, context=context)
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if isinstance(result, NonStreamingResult):
        return Response(content=result.json, media_type="application/json")
    raise HTTPException(status_code=500, detail="Unexpected ChatKit response type")


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
