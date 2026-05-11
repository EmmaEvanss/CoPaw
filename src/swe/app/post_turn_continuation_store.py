# -*- coding: utf-8 -*-
"""In-memory store for post-turn continuation confirmations."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

_DEFAULT_TENANT = "default"
_DEFAULT_TTL_SECONDS = 600
_lock = asyncio.Lock()
_continuations: Dict[str, "PendingContinuation"] = {}


@dataclass(slots=True)
class PendingContinuation:
    validation_id: str
    session_id: str
    user_message: str
    assistant_response: str
    reason: str
    follow_up_prompt: str
    tenant_id: str
    created_at: float
    expires_at: float
    confirmed_turn_index: int
    status: str = "pending"


def _tenant_key(tenant_id: Optional[str]) -> str:
    return tenant_id or _DEFAULT_TENANT


def _is_expired(entry: PendingContinuation, now: Optional[float] = None) -> bool:
    return entry.expires_at <= (now if now is not None else time.time())


def _public_entry(
    entry: PendingContinuation,
    *,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": entry.validation_id,
        "status": status or (
            "needs_confirmation"
            if entry.status == "pending"
            else entry.status
        ),
        "completed": False,
        "reason": entry.reason,
        "session_id": entry.session_id,
        "expires_at": int(entry.expires_at),
    }


def _prune_expired(now: Optional[float] = None) -> None:
    current = now if now is not None else time.time()
    expired_ids = [
        validation_id
        for validation_id, entry in _continuations.items()
        if _is_expired(entry, current)
    ]
    for validation_id in expired_ids:
        _continuations.pop(validation_id, None)


async def store_pending_continuation(
    *,
    session_id: str,
    user_message: str,
    assistant_response: str,
    reason: str,
    follow_up_prompt: str,
    tenant_id: Optional[str] = None,
    confirmed_turn_index: int = 0,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> Dict[str, Any]:
    """Store the latest continuation prompt for user confirmation."""
    validation_id = f"validation_{uuid.uuid4().hex}"
    now = time.time()
    entry = PendingContinuation(
        validation_id=validation_id,
        session_id=session_id,
        user_message=user_message,
        assistant_response=assistant_response,
        reason=reason,
        follow_up_prompt=follow_up_prompt,
        tenant_id=_tenant_key(tenant_id),
        created_at=now,
        expires_at=now + ttl_seconds,
        confirmed_turn_index=confirmed_turn_index,
    )

    async with _lock:
        _prune_expired(now)
        _continuations[validation_id] = entry

    return _public_entry(entry)


async def peek_latest_pending_continuation(
    *,
    session_id: str,
    tenant_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the latest unclaimed continuation for a session."""
    tenant_key = _tenant_key(tenant_id)
    async with _lock:
        _prune_expired()
        candidates = [
            entry
            for entry in _continuations.values()
            if entry.session_id == session_id
            and entry.tenant_id == tenant_key
            and entry.status == "pending"
        ]
        if not candidates:
            return None
        entry = max(candidates, key=lambda item: item.created_at)
        return _public_entry(entry)


async def claim_pending_continuation(
    *,
    validation_id: str,
    session_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Mark a continuation as confirmed without exposing its prompt."""
    tenant_key = _tenant_key(tenant_id)
    async with _lock:
        _prune_expired()
        entry = _continuations.get(validation_id)
        if entry is None:
            return None
        if entry.tenant_id != tenant_key:
            return None
        if session_id is not None and entry.session_id != session_id:
            return None
        if entry.status != "pending":
            return None
        entry.status = "consumed"
        return _public_entry(entry, status="consumed")


async def consume_pending_continuation(
    *,
    validation_id: str,
    session_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[PendingContinuation]:
    """Consume and remove a continuation prompt for runner execution."""
    tenant_key = _tenant_key(tenant_id)
    async with _lock:
        _prune_expired()
        entry = _continuations.get(validation_id)
        if entry is None:
            return None
        if entry.tenant_id != tenant_key:
            return None
        if session_id is not None and entry.session_id != session_id:
            return None
        _continuations.pop(validation_id, None)
        return entry


async def clear_pending_continuations() -> None:
    """Clear store contents. Intended for tests."""
    async with _lock:
        _continuations.clear()
