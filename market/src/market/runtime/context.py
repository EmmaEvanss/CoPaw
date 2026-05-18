# -*- coding: utf-8 -*-
"""market 内部使用的租户上下文与 tenant 解析工具。"""

from __future__ import annotations

import base64
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
_SCOPE_ID_PREFIX = "scope.v1"
_IDENTITY_MAX_LENGTH = 256


def is_valid_identity_value(identity: str) -> bool:
    """按主服务规则校验 tenant/source 原始身份值。"""
    if not identity:
        return False
    if len(identity) < 1 or len(identity) > _IDENTITY_MAX_LENGTH:
        return False
    if ".." in identity or "/" in identity or "\\" in identity:
        return False
    if any(ord(char) < 32 for char in identity):
        return False
    return True


def _encode_scope_component(value: str) -> str:
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode(
        "ascii",
    )
    return encoded.rstrip("=")


def encode_scope_id(tenant_id: str, source_id: str) -> str:
    """按主服务一致规则编码运行时 scope 标识。"""
    if not is_valid_identity_value(tenant_id):
        raise ValueError("Invalid tenant_id for scope encoding")
    if not is_valid_identity_value(source_id):
        raise ValueError("Invalid source_id for scope encoding")
    return ".".join(
        (
            _SCOPE_ID_PREFIX,
            _encode_scope_component(tenant_id),
            _encode_scope_component(source_id),
        ),
    )


def resolve_effective_tenant_id(
    tenant_id: str,
    source_id: str | None,
) -> str:
    """解析 market 本地状态使用的运行时 scope 标识。"""
    if not source_id:
        return tenant_id
    return encode_scope_id(tenant_id, source_id)


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
