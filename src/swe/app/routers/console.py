# -*- coding: utf-8 -*-
"""Console APIs: push messages, chat, and file upload for chat."""
from __future__ import annotations

import json
import logging
import re
import asyncio
import uuid
from pathlib import Path
from typing import AsyncGenerator, Union, Any, Optional, Dict

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    Body,
)
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from ..agent_context import get_agent_for_request


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/console", tags=["console"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_RECONNECT_ATTACH_ATTEMPTS = 10
_RECONNECT_ATTACH_RETRY_DELAY_SECONDS = 0.1
_CONSOLE_SSE_HEARTBEAT_SECONDS = 15


async def _stream_with_keepalive(
    source: AsyncGenerator[str, None],
    interval: float = _CONSOLE_SSE_HEARTBEAT_SECONDS,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE generator with keepalive comment frames.

    When no real event arrives within *interval* seconds, emits an SSE
    comment line ``: keep-alive\\n\\n`` which is ignored by EventSource
    but keeps reverse proxies (nginx, ALB) from closing the connection
    due to idle timeout.
    """

    async def _next_item(
        it: AsyncGenerator[str, None],
    ) -> tuple[str, bool]:
        """Return (event, True) or ('', False) when the iterator is done."""
        try:
            return await it.__anext__(), True
        except StopAsyncIteration:
            return "", False

    pending = asyncio.ensure_future(_next_item(source))
    try:
        while True:
            done, _ = await asyncio.wait(
                (pending,),
                timeout=interval,
            )
            if done:
                event_data, has_more = pending.result()
                if not has_more:
                    return
                yield event_data
                pending = asyncio.ensure_future(_next_item(source))
            else:
                # No real event within interval — send keepalive
                yield ": keep-alive\n\n"
    finally:
        pending.cancel()
        try:
            await pending
        except (asyncio.CancelledError, StopAsyncIteration):
            pass


def _safe_filename(name: str) -> str:
    """Safe basename, alphanumeric/./-/_, max 200 chars."""
    base = Path(name).name if name else "file"
    return re.sub(r"[^\w.\-]", "_", base)[:200] or "file"


def _extract_session_and_payload(request_data: Union[AgentRequest, dict]):
    """Extract run_key (ChatSpec.id), session_id, and native payload.

    Align with qwenpaw: keep full multimodal content parts (text/file/image/audio/video)
    instead of dropping non-text blocks.

    run_key must be ChatSpec.id (chat_id) so it matches list_chats/get_chat.
    """
    if isinstance(request_data, AgentRequest):
        channel_id = getattr(request_data, "channel", None) or "console"
        sender_id = request_data.user_id or "default"
        session_id = request_data.session_id or "default"
        content_parts = (
            list(request_data.input[0].content) if request_data.input else []
        )
    else:
        channel_id = request_data.get("channel", "console")
        sender_id = request_data.get("user_id", "default")
        session_id = request_data.get("session_id", "default")
        input_data = request_data.get("input", [])

        content_parts = []
        for content_part in input_data:
            # pydantic model (rare in this branch) or plain dict
            if hasattr(content_part, "content"):
                content_parts.extend(list(content_part.content or []))
            elif isinstance(content_part, dict) and "content" in content_part:
                content_parts.extend(content_part.get("content") or [])

    native_payload = {
        "channel_id": channel_id,
        "sender_id": sender_id,
        "content_parts": content_parts,
        "meta": {
            "session_id": session_id,
            "user_id": sender_id,
        },
    }
    return native_payload


def _derive_chat_name(native_payload: dict) -> str:
    """Build a display name for a newly created chat."""
    if not native_payload["content_parts"]:
        return "New Chat"

    content = native_payload["content_parts"][0]
    if not content:
        return "Media Message"
    if isinstance(content, dict):
        return content.get("text", "New Chat")[:10]
    if hasattr(content, "text"):
        return content.text[:10]
    return "Media Message"


async def _attach_reconnect_queue(
    workspace,
    tracker,
    session_id: str,
    channel_id: str,
) -> tuple[asyncio.Queue, str]:
    """Attach to a running chat by chat_id or logical session_id."""
    for attempt in range(_RECONNECT_ATTACH_ATTEMPTS):
        chat = await workspace.chat_manager.get_chat(session_id)
        if chat is not None:
            queue = await tracker.attach(chat.id)
            if queue is not None:
                return queue, chat.id

        chat_id = await workspace.chat_manager.get_chat_id_by_session(
            session_id,
            channel_id,
        )
        if chat_id is not None:
            queue = await tracker.attach(chat_id)
            if queue is not None:
                return queue, chat_id

        if attempt < _RECONNECT_ATTACH_ATTEMPTS - 1:
            await asyncio.sleep(_RECONNECT_ATTACH_RETRY_DELAY_SECONDS)

    raise HTTPException(
        status_code=404,
        detail="No running chat for this session",
    )


@router.post(
    "/chat",
    status_code=200,
    summary="Chat with console (streaming response)",
    description="Agent API Request Format. See runtime.agentscope.io. "
    "Use body.reconnect=true to attach to a running stream.",
)
async def post_console_chat(
    request_data: Union[AgentRequest, dict],
    request: Request,
) -> StreamingResponse:
    """Stream agent response. Run continues in background after disconnect.
    Stop via POST /console/chat/stop. Reconnect with body.reconnect=true.
    """
    workspace = await get_agent_for_request(request)
    console_channel = await workspace.channel_manager.get_channel("console")
    if console_channel is None:
        raise HTTPException(
            status_code=503,
            detail="Channel Console not found",
        )
    try:
        native_payload = _extract_session_and_payload(request_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Inject source_id from header for data isolation
    source_id = request.headers.get("X-Source-Id", "default")
    native_payload["meta"]["source_id"] = source_id

    # Debug: log the session_id from frontend
    logger.debug(
        "Console chat: native_payload.meta.session_id=%s",
        native_payload.get("meta", {}).get("session_id"),
    )
    session_id = console_channel.resolve_session_id(
        sender_id=native_payload["sender_id"],
        channel_meta=native_payload["meta"],
    )
    logger.debug(
        "Console chat: resolved session_id=%s",
        session_id,
    )
    tracker = workspace.task_tracker

    is_reconnect = False
    if isinstance(request_data, dict):
        is_reconnect = request_data.get("reconnect") is True

    if is_reconnect:
        queue, run_key = await _attach_reconnect_queue(
            workspace,
            tracker,
            session_id,
            native_payload["channel_id"],
        )
        if queue is None:
            raise HTTPException(
                status_code=404,
                detail="No running chat for this session",
            )
    else:
        chat = await workspace.chat_manager.get_or_create_chat(
            session_id,
            native_payload["sender_id"],
            native_payload["channel_id"],
            name=_derive_chat_name(native_payload),
            meta={
                "agent_id": workspace.agent_id,
            }
            if getattr(workspace, "agent_id", None)
            else None,
        )
        queue, _ = await tracker.attach_or_start(
            chat.id,
            native_payload,
            console_channel.stream_one,
        )
        run_key = chat.id

    async def event_generator() -> AsyncGenerator[str, None]:
        # Hold iterator so finally can aclose(); guarantees stream_from_queue's
        # finally (detach_subscriber) on client abort / generator teardown.
        stream_it = tracker.stream_from_queue(queue, run_key)
        try:
            try:
                async for event_data in stream_it:
                    yield event_data
            except Exception as e:
                logger.exception("Console chat stream error")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            await stream_it.aclose()

    return StreamingResponse(
        _stream_with_keepalive(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/chat/stop",
    status_code=200,
    summary="Stop running console chat",
)
async def post_console_chat_stop(
    request: Request,
    chat_id: str = Query(..., description="Chat id (ChatSpec.id) to stop"),
) -> dict:
    """Stop the running chat. Only stops when called."""
    workspace = await get_agent_for_request(request)
    stopped = await workspace.task_tracker.request_stop(chat_id)
    return {"stopped": stopped}


@router.post("/upload", response_model=dict, summary="Upload file for chat")
async def post_console_upload(
    request: Request,
    file: UploadFile = File(..., description="File to attach"),
) -> dict:
    """Save to console channel media_dir."""

    workspace = await get_agent_for_request(request)
    console_channel = await workspace.channel_manager.get_channel("console")
    if console_channel is None:
        raise HTTPException(
            status_code=503,
            detail="Channel Console not found",
        )
    media_dir = console_channel.media_dir
    media_dir.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File too large (max "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    safe_name = _safe_filename(file.filename or "file")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"

    path = (media_dir / stored_name).resolve()
    path.write_bytes(data)
    return {
        "url": path,
        "file_name": safe_name,
        "size": len(data),
    }


@router.get("/push-messages")
async def get_push_messages(
    request: Request,
    session_id: str | None = Query(None, description="Session id"),
):
    """Return pending push messages for the current tenant session.

    If session_id is provided, returns messages for that specific session.
    If session_id is not provided, returns all messages for the tenant.
    """
    from ..console_push_store import take, take_all

    tenant_id = getattr(request.state, "tenant_id", None)

    if session_id:
        messages = await take(session_id, tenant_id=tenant_id)
    else:
        messages = await take_all(tenant_id=tenant_id)

    return {"messages": messages}


@router.get("/suggestions")
async def get_suggestions(
    request: Request,
    session_id: str = Query(
        ...,
        description="Session id to get suggestions for",
    ),
):
    """Return generated suggestions for the session.

    猜你想问建议在后台异步生成，前端在主响应完成后轮询此接口获取。
    获取后建议会被移除，不会重复返回。
    """
    from ..suggestions import take_suggestions

    tenant_id = getattr(request.state, "tenant_id", None)
    suggestions = await take_suggestions(session_id, tenant_id=tenant_id)
    return {"suggestions": suggestions}


class QAContentRequest(BaseModel):
    """Q&A 内容请求模型."""

    chat_id: str = Field(..., description="Chat id (backend chat.id)")
    user_message: str = Field(..., description="User message text")


class QAContentResponse(BaseModel):
    """Q&A 内容响应模型."""

    success: bool = Field(..., description="Whether Q&A content was found")
    qa_content: Optional[Dict[str, str]] = Field(
        default=None,
        description="Extracted Q&A content (user_message, assistant_response)",
    )


@router.post("/suggestions/qa-content", response_model=QAContentResponse)
async def get_suggestions_qa_content(
    request: Request,
    body: QAContentRequest,
):
    """根据用户问题获取后端提取的 Q&A 内容.

    前端在响应完成后调用此接口，获取后端提取的 Q&A 关键内容，
    用于调用外部 suggestions API。

    Args:
        chat_id: 后端 chat.id（UUID）
        user_message: 用户问题文本（用于匹配）

    Returns:
        success: 是否找到 Q&A 内容
        qa_content: 提取后的用户问题和助手回答（总长度不超过配置上限）
    """
    from ..suggestions import get_qa_content

    tenant_id = getattr(request.state, "tenant_id", None)

    entry = await get_qa_content(
        chat_id=body.chat_id,
        user_message=body.user_message,
        tenant_id=tenant_id,
    )

    if entry is None:
        return QAContentResponse(
            success=False,
            qa_content=None,
        )

    return QAContentResponse(
        success=True,
        qa_content=entry,
    )
