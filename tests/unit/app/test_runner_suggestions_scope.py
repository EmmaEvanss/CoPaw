# -*- coding: utf-8 -*-
"""Runner background suggestion scope regression tests."""

from unittest.mock import AsyncMock

import pytest
from agentscope.message import Msg
from swe.config.config import SuggestionMode

from swe.app.runner import runner as runner_module


class _SuggestionConfig:
    max_suggestions = 3
    timeout_seconds = 10
    user_message_max_length = 200
    assistant_response_max_length = 400


class _QAOnlySuggestionConfig:
    enabled = True
    mode = SuggestionMode.QA_EXTRACTION_ONLY
    user_message_max_length = 200
    assistant_response_max_length = 400
    qa_content_total_max_length = 800


@pytest.mark.asyncio
async def test_generate_and_store_suggestions_passes_scope_tenant(
    monkeypatch,
) -> None:
    generate = AsyncMock(return_value=["next question"])
    store = AsyncMock(return_value=None)
    monkeypatch.setattr(runner_module, "generate_suggestions", generate)
    monkeypatch.setattr(runner_module, "store_suggestions", store)

    await runner_module._generate_and_store_suggestions(
        "session-a",
        "user says hi",
        "assistant replies",
        _SuggestionConfig(),
        tenant_id="scope.v1.dGVuYW50LWE.c291cmNlLWE",
    )

    store.assert_awaited_once_with(
        "session-a",
        ["next question"],
        tenant_id="dGVuYW50LWE.c291cmNlLWE",
    )


@pytest.mark.asyncio
async def test_store_pending_continuation_passes_scope_tenant(
    monkeypatch,
) -> None:
    store = AsyncMock(return_value={"id": "validation-1"})
    monkeypatch.setattr(runner_module, "store_pending_continuation", store)

    runner = runner_module.AgentRunner(
        agent_id="agent-a",
        tenant_id="scope.v1.dGVuYW50LWE.c291cmNlLWE",
    )
    runtime = type("Runtime", (), {"session_id": "session-a", "agent": None})()
    plan = type(
        "Plan",
        (),
        {
            "original_user_message": "帮我继续",
            "confirmed_turn_index": 0,
            "validation_config": type(
                "ValidationConfig",
                (),
                {"max_confirmed_turns": 2},
            )(),
        },
    )()
    outcome = type(
        "Outcome",
        (),
        {
            "task_completed": False,
            "last_validation_result": type(
                "ValidationResult",
                (),
                {
                    "reason": "still work left",
                    "follow_up_prompt": "继续处理剩余步骤",
                },
            )(),
            "auto_follow_up_turns": 0,
            "max_auto_turns": 2,
        },
    )()

    await runner._store_pending_validation_if_needed(
        runtime=runtime,
        plan=plan,
        outcome=outcome,
    )

    store.assert_awaited_once_with(
        session_id="session-a",
        user_message="帮我继续",
        assistant_response="",
        reason="still work left",
        follow_up_prompt="继续处理剩余步骤",
        tenant_id="dGVuYW50LWE.c291cmNlLWE",
        confirmed_turn_index=0,
    )


@pytest.mark.asyncio
async def test_store_qa_content_passes_scope_tenant(monkeypatch) -> None:
    store = AsyncMock(return_value=None)
    monkeypatch.setattr("swe.app.suggestions.store.store_qa_content", store)

    runner = runner_module.AgentRunner(
        agent_id="agent-a",
        tenant_id="scope.v1.dGVuYW50LWE.c291cmNlLWE",
    )
    runtime = type(
        "Runtime",
        (),
        {
            "chat": type("Chat", (), {"id": "chat-a"})(),
            "agent": type(
                "Agent",
                (),
                {
                    "memory": type(
                        "Memory",
                        (),
                        {
                            "content": [
                                (
                                    Msg(
                                        name="Friday",
                                        role="assistant",
                                        content="整理后的答案",
                                    ),
                                    [],
                                ),
                            ],
                        },
                    )(),
                },
            )(),
            "agent_config": type(
                "AgentConfig",
                (),
                {
                    "running": type(
                        "Running",
                        (),
                        {"suggestions": _QAOnlySuggestionConfig()},
                    )(),
                },
            )(),
        },
    )()
    outcome = type("Outcome", (), {"task_completed": True})()

    await runner._store_qa_content_if_needed(
        runtime=runtime,
        query="请帮我整理一下",
        outcome=outcome,
    )

    store.assert_awaited_once_with(
        chat_id="chat-a",
        user_message="请帮我整理一下",
        assistant_response="整理后的答案",
        tenant_id="dGVuYW50LWE.c291cmNlLWE",
    )
