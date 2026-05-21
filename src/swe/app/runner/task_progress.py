# -*- coding: utf-8 -*-
"""Explicit task progress state for chat streaming."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Literal

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentResponse,
    Message,
)
from pydantic import BaseModel, Field, model_validator

TaskStepStatus = Literal["todo", "running", "done"]
TaskPhaseStatus = Literal["active", "completed", "cancelled"]


class TaskProgressItem(BaseModel):
    id: str = Field(default="")
    label: str = Field(default="")
    status: TaskStepStatus

    model_config = {"extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        """将模型可能传入的 title 字段映射为 label，自动补全 id。"""
        if isinstance(data, dict):
            if "label" not in data and "title" in data:
                data = {**data, "label": data["title"]}
            if "id" not in data or not data.get("id"):
                data["id"] = data.get("label", "") or uuid.uuid4().hex[:8]
        return data


class TaskProgressPayload(BaseModel):
    turn_id: str
    phase_status: TaskPhaseStatus
    version: int
    current_step_index: int | None = None
    total_steps: int
    title: str | None = None
    items: list[TaskProgressItem] = Field(default_factory=list)


class ProgressAgentResponse(AgentResponse):
    task_progress: TaskProgressPayload | None = None


class ProgressMessage(Message):
    task_progress: TaskProgressPayload | None = None


def normalize_task_progress_payload(
    *,
    turn_id: str,
    title: str | None,
    items: list[dict[str, Any]] | list[TaskProgressItem],
    current_step_index: int | None,
    version: int,
    phase_status: TaskPhaseStatus,
) -> TaskProgressPayload:
    normalized_items = [
        (
            item
            if isinstance(item, TaskProgressItem)
            else TaskProgressItem(**item)
        )
        for item in items
    ]
    running_index: int | None = None
    for index, item in enumerate(normalized_items):
        if item.status == "running":
            running_index = index + 1
            break

    if current_step_index is None:
        current_step_index = running_index

    if current_step_index is not None and not 1 <= current_step_index <= len(
        normalized_items,
    ):
        current_step_index = running_index

    return TaskProgressPayload(
        turn_id=turn_id,
        phase_status=phase_status,
        version=version,
        current_step_index=current_step_index,
        total_steps=len(normalized_items),
        title=title,
        items=normalized_items,
    )


def attach_task_progress(
    event: Any,
    task_progress: TaskProgressPayload | None,
    *,
    enabled: bool = True,
) -> Any:
    if not enabled or task_progress is None:
        return event

    payload = task_progress.model_dump(mode="json")
    if isinstance(event, AgentResponse):
        return ProgressAgentResponse(
            **event.model_dump(mode="json"),
            task_progress=payload,
        )
    if isinstance(event, Message):
        return ProgressMessage(
            **event.model_dump(mode="json"),
            task_progress=payload,
        )
    return event


def clone_task_progress(
    payload: TaskProgressPayload | None,
) -> TaskProgressPayload | None:
    return copy.deepcopy(payload) if payload is not None else None


__all__ = [
    "ProgressAgentResponse",
    "ProgressMessage",
    "TaskProgressItem",
    "TaskProgressPayload",
    "attach_task_progress",
    "clone_task_progress",
    "normalize_task_progress_payload",
]
