# -*- coding: utf-8 -*-
"""market 内部使用的租户上下文与 tenant 解析工具。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Generator

current_tenant_id: ContextVar[str | None] = ContextVar(
    "market_current_tenant_id",
    default=None,
)
current_user_id: ContextVar[str | None] = ContextVar(
    "market_current_user_id",
    default=None,
)
current_workspace_dir: ContextVar[Path | None] = ContextVar(
    "market_current_workspace_dir",
    default=None,
)
current_source_id: ContextVar[str | None] = ContextVar(
    "market_current_source_id",
    default=None,
)


def resolve_effective_tenant_id(
    tenant_id: str,
    source_id: str | None,
) -> str:
    """解析默认租户在带来源场景下的实际目录名。"""
    if tenant_id == "default":
        if source_id:
            return f"default_{source_id}"
        return "default"
    return tenant_id


@contextmanager
def tenant_context(
    tenant_id: str | None = None,
    user_id: str | None = None,
    workspace_dir: Path | None = None,
    source_id: str | None = None,
) -> Generator[None, None, None]:
    """在当前协程上下文中临时绑定租户信息。"""
    tokens: list[tuple[ContextVar, Token]] = []
    try:
        if tenant_id is not None:
            tokens.append(
                (current_tenant_id, current_tenant_id.set(tenant_id)),
            )
        if user_id is not None:
            tokens.append((current_user_id, current_user_id.set(user_id)))
        if workspace_dir is not None:
            tokens.append(
                (
                    current_workspace_dir,
                    current_workspace_dir.set(workspace_dir),
                ),
            )
        if source_id is not None:
            tokens.append(
                (current_source_id, current_source_id.set(source_id)),
            )
        yield
    finally:
        for context_var, token in reversed(tokens):
            context_var.reset(token)
