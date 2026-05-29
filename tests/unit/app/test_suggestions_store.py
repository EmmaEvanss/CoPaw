# -*- coding: utf-8 -*-
"""猜你想问 Q&A 内容存储的回归测试。"""

from __future__ import annotations

import uuid

import pytest

from src.swe.app.suggestions.store import get_qa_content, store_qa_content
from swe.config.context import tenant_context


@pytest.mark.asyncio
async def test_get_qa_content_matches_by_normalized_user_message() -> None:
    chat_id = f"chat-{uuid.uuid4()}"

    await store_qa_content(
        chat_id=chat_id,
        user_message="  HELLO WORLD  ",
        assistant_response="answer",
        tenant_id="tenant-a",
    )

    result = await get_qa_content(
        chat_id=chat_id,
        user_message="hello world",
        tenant_id="tenant-a",
    )

    assert result == {
        "user_message": "  HELLO WORLD  ",
        "assistant_response": "answer",
    }


@pytest.mark.asyncio
async def test_get_qa_content_matches_full_query_after_store_truncation() -> (
    None
):
    chat_id = f"chat-{uuid.uuid4()}"
    long_user_message = "问题" * 150

    await store_qa_content(
        chat_id=chat_id,
        user_message=long_user_message[:200],
        assistant_response="answer",
        tenant_id="tenant-a",
    )

    result = await get_qa_content(
        chat_id=chat_id,
        user_message=long_user_message,
        tenant_id="tenant-a",
    )

    assert result is not None
    assert result["assistant_response"] == "answer"


@pytest.mark.asyncio
async def test_get_qa_content_rejects_tenant_mismatch() -> None:
    chat_id = f"chat-{uuid.uuid4()}"

    await store_qa_content(
        chat_id=chat_id,
        user_message="same question",
        assistant_response="answer",
        tenant_id="tenant-a",
    )

    result = await get_qa_content(
        chat_id=chat_id,
        user_message="same question",
        tenant_id="tenant-b",
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_qa_content_rejects_source_scope_mismatch_with_same_tenant() -> (
    None
):
    chat_id = f"chat-{uuid.uuid4()}"

    with tenant_context(tenant_id="tenant-a", source_id="source-a"):
        await store_qa_content(
            chat_id=chat_id,
            user_message="same question",
            assistant_response="answer",
            tenant_id="tenant-a",
        )

    with tenant_context(tenant_id="tenant-a", source_id="source-b"):
        result = await get_qa_content(
            chat_id=chat_id,
            user_message="same question",
            tenant_id="tenant-a",
        )

    assert result is None


@pytest.mark.asyncio
async def test_legacy_scope_input_is_retrievable_via_canonical_scope() -> None:
    chat_id = f"chat-{uuid.uuid4()}"

    await store_qa_content(
        chat_id=chat_id,
        user_message="same question",
        assistant_response="answer",
        tenant_id="scope.v1.dGVuYW50LWE.c291cmNlLWE",
    )

    result = await get_qa_content(
        chat_id=chat_id,
        user_message="same question",
        tenant_id="dGVuYW50LWE.c291cmNlLWE",
    )

    assert result == {
        "user_message": "same question",
        "assistant_response": "answer",
    }
