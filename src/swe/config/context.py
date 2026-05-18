# -*- coding: utf-8 -*-
"""Context variables for tenant isolation and workspace directory.

This module provides context variables to pass tenant identity, user identity,
and workspace directory to tool functions, enabling strict tenant isolation
in a multi-tenant environment.
"""

import base64
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Generator
from contextlib import contextmanager

# Context variable to store the current tenant ID
current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id",
    default=None,
)

# Context variable to store the current user ID
current_user_id: ContextVar[str | None] = ContextVar(
    "current_user_id",
    default=None,
)

# Context variable to store the current agent's workspace directory
current_workspace_dir: ContextVar[Path | None] = ContextVar(
    "current_workspace_dir",
    default=None,
)

# Context variable to store the current source ID (from X-Source-Id header)
current_source_id: ContextVar[str | None] = ContextVar(
    "current_source_id",
    default=None,
)

# Context variable to store the current runtime scope ID
current_scope_id: ContextVar[str | None] = ContextVar(
    "current_scope_id",
    default=None,
)

_SCOPE_ID_PREFIX = "scope.v1"
_IDENTITY_MAX_LENGTH = 256


def get_current_tenant_id() -> str | None:
    """Get the current tenant ID from context.

    Returns:
        The current tenant ID, or None if not set.
    """
    return current_tenant_id.get()


def set_current_tenant_id(tenant_id: str | None) -> Token:
    """Set the current tenant ID in context.

    Args:
        tenant_id: The tenant ID to set.

    Returns:
        Token for resetting the context variable.
    """
    return current_tenant_id.set(tenant_id)


def reset_current_tenant_id(token: Token) -> None:
    """Reset the current tenant ID using a token.

    Args:
        token: The token returned by set_current_tenant_id.
    """
    current_tenant_id.reset(token)


def get_current_user_id() -> str | None:
    """Get the current user ID from context.

    Returns:
        The current user ID, or None if not set.
    """
    return current_user_id.get()


def set_current_user_id(user_id: str | None) -> Token:
    """Set the current user ID in context.

    Args:
        user_id: The user ID to set.

    Returns:
        Token for resetting the context variable.
    """
    return current_user_id.set(user_id)


def reset_current_user_id(token: Token) -> None:
    """Reset the current user ID using a token.

    Args:
        token: The token returned by set_current_user_id.
    """
    current_user_id.reset(token)


def get_current_source_id() -> str | None:
    """Get the current source ID from context.

    Returns:
        The current source ID, or None if not set.
    """
    return current_source_id.get()


def get_current_scope_id() -> str | None:
    """Get the current runtime scope ID from context."""
    return current_scope_id.get()


def set_current_scope_id(scope_id: str | None) -> Token:
    """Set the current runtime scope ID in context."""
    return current_scope_id.set(scope_id)


def reset_current_scope_id(token: Token) -> None:
    """Reset the current runtime scope ID using a token."""
    current_scope_id.reset(token)


def is_valid_identity_value(identity: str) -> bool:
    """Validate a raw tenant/source identity component."""
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


def _decode_scope_component(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(
        (value + padding).encode("ascii"),
    ).decode("utf-8")


def encode_scope_id(tenant_id: str, source_id: str) -> str:
    """Encode a reversible runtime scope ID from tenant/source."""
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


def decode_scope_id(scope_id: str) -> tuple[str, str]:
    """Decode a runtime scope ID back to logical tenant/source."""
    prefix = f"{_SCOPE_ID_PREFIX}."
    if not scope_id.startswith(prefix):
        raise ValueError("Invalid scope_id prefix")
    parts = scope_id[len(prefix) :].split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid scope_id payload")
    return (
        _decode_scope_component(parts[0]),
        _decode_scope_component(parts[1]),
    )


def resolve_scope_id(
    tenant_id: str | None,
    source_id: str | None,
) -> str | None:
    """Resolve a runtime scope ID when both tenant and source are present."""
    if tenant_id is None or source_id is None:
        return None
    return encode_scope_id(tenant_id, source_id)


def resolve_runtime_tenant_id(
    tenant_id: str | None,
    source_id: str | None,
) -> str | None:
    """解析运行时存储和工作区使用的租户标识。

    该函数需要同时兼容逻辑租户和已编码的 scope。调用方可能已经通过
    middleware 解析过 ``scope_id``，这里必须保持幂等，避免把 scope 当作
    普通租户再次和 ``source_id`` 组合编码。
    """
    if tenant_id is None:
        return None
    try:
        decode_scope_id(tenant_id)
    except ValueError:
        pass
    else:
        return tenant_id
    scope_id = resolve_scope_id(tenant_id, source_id)
    if scope_id is not None:
        return scope_id
    return tenant_id


def resolve_runtime_identity(
    runtime_tenant_id: str | None,
    source_id: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """展开运行时身份，返回 logical tenant、source 与 scope。

    Args:
        runtime_tenant_id: 运行时租户标识，既可能是逻辑 tenant，
            也可能已经是编码后的 ``scope_id``。
        source_id: 显式来源标识；当 ``runtime_tenant_id`` 仍是逻辑
            tenant 时用于补齐 ``scope_id``。

    Returns:
        ``(tenant_id, source_id, scope_id)`` 三元组。若传入的
        ``runtime_tenant_id`` 已经是编码后的 scope，则会优先解码并
        返回原始 tenant/source，避免后台任务只携带 opaque key。
    """
    if runtime_tenant_id is None:
        return (None, source_id, None)

    try:
        tenant_id, decoded_source_id = decode_scope_id(runtime_tenant_id)
    except ValueError:
        scope_id = resolve_scope_id(runtime_tenant_id, source_id)
        return (runtime_tenant_id, source_id, scope_id)

    return (tenant_id, decoded_source_id, runtime_tenant_id)


def set_current_source_id(source_id: str | None) -> Token:
    """Set the current source ID in context.

    Args:
        source_id: The source ID to set.

    Returns:
        Token for resetting the context variable.
    """
    return current_source_id.set(source_id)


def reset_current_source_id(token: Token) -> None:
    """Reset the current source ID using a token.

    Args:
        token: The token returned by set_current_source_id.
    """
    current_source_id.reset(token)


def get_current_workspace_dir() -> Path | None:
    """Get the current agent's workspace directory from context.

    Returns:
        Path to the current agent's workspace directory, or None if not set.
    """
    return current_workspace_dir.get()


def get_current_effective_tenant_id() -> str | None:
    """Get the current runtime tenant ID with default+source isolation."""
    scope_id = get_current_scope_id()
    if scope_id is not None:
        return scope_id
    return resolve_runtime_tenant_id(
        get_current_tenant_id(),
        get_current_source_id(),
    )


def set_current_workspace_dir(workspace_dir: Path | None) -> Token:
    """Set the current agent's workspace directory in context.

    Args:
        workspace_dir: Path to the agent's workspace directory.

    Returns:
        Token for resetting the context variable.
    """
    return current_workspace_dir.set(workspace_dir)


def reset_current_workspace_dir(token: Token) -> None:
    """Reset the current workspace directory using a token.

    Args:
        token: The token returned by set_current_workspace_dir.
    """
    current_workspace_dir.reset(token)


class TenantContextError(RuntimeError):
    """Raised when tenant context is required but not available."""


def get_current_tenant_id_strict() -> str:
    """Get the current tenant ID, raising if not set.

    Returns:
        The current tenant ID.

    Raises:
        TenantContextError: If tenant ID is not set in context.
    """
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextError(
            "Tenant ID is not set in context. "
            "Ensure this code runs within a tenant-scoped request or context.",
        )
    return tenant_id


def get_current_user_id_strict() -> str:
    """Get the current user ID, raising if not set.

    Returns:
        The current user ID.

    Raises:
        TenantContextError: If user ID is not set in context.
    """
    user_id = current_user_id.get()
    if user_id is None:
        raise TenantContextError(
            "User ID is not set in context. "
            "Ensure this code runs within a tenant-scoped request or context.",
        )
    return user_id


def get_current_workspace_dir_strict() -> Path:
    """Get the current workspace directory, raising if not set.

    Returns:
        Path to the current workspace directory.

    Raises:
        TenantContextError: If workspace directory is not set in context.
    """
    workspace_dir = current_workspace_dir.get()
    if workspace_dir is None:
        raise TenantContextError(
            "Workspace directory is not set in context. "
            "Ensure this code runs within a tenant-scoped request or context.",
        )
    return workspace_dir


@contextmanager
def tenant_context(
    tenant_id: str | None = None,
    user_id: str | None = None,
    workspace_dir: Path | None = None,
    source_id: str | None = None,
    scope_id: str | None = None,
) -> Generator[None, None, None]:
    """Context manager for binding tenant context.

    Temporarily sets tenant_id, user_id, workspace_dir, source_id, and
    scope_id
    in context, restoring previous values on exit.

    Args:
        tenant_id: The tenant ID to set.
        user_id: The user ID to set.
        workspace_dir: The workspace directory to set.
        source_id: The source ID to set.
        scope_id: The runtime scope ID to set. If omitted, resolve from
            tenant_id/source_id when possible.

    Yields:
        None

    Example:
        with tenant_context(tenant_id="acme", user_id="alice"):
            # Code here has access to tenant context
            process_request()
        # Context restored after exit
    """
    tokens: list[tuple[str, Token[Any]]] = []
    resolved_scope_id = scope_id or resolve_scope_id(tenant_id, source_id)
    try:
        if tenant_id is not None:
            tokens.append(("tenant", current_tenant_id.set(tenant_id)))
        if user_id is not None:
            tokens.append(("user", current_user_id.set(user_id)))
        if workspace_dir is not None:
            tokens.append(
                ("workspace", current_workspace_dir.set(workspace_dir)),
            )
        if source_id is not None:
            tokens.append(("source", current_source_id.set(source_id)))
        if resolved_scope_id is not None:
            tokens.append(("scope", current_scope_id.set(resolved_scope_id)))
        yield
    finally:
        for name, token in reversed(tokens):
            if name == "tenant":
                current_tenant_id.reset(token)
            elif name == "user":
                current_user_id.reset(token)
            elif name == "workspace":
                current_workspace_dir.reset(token)
            elif name == "source":
                current_source_id.reset(token)
            elif name == "scope":
                current_scope_id.reset(token)


# Context variable to store the recent_max_bytes limit
current_recent_max_bytes: ContextVar[int | None] = ContextVar(
    "current_recent_max_bytes",
    default=None,
)


def get_current_recent_max_bytes() -> int | None:
    """Get the current agent's recent_max_bytes limit from context.

    Returns:
        Byte limit for recent tool output truncation, or None if not set.
    """
    return current_recent_max_bytes.get()


def set_current_recent_max_bytes(max_bytes: int | None) -> None:
    """Set the current agent's recent_max_bytes limit in context.

    Args:
        max_bytes: Byte limit for recent tool output truncation.
    """
    current_recent_max_bytes.set(max_bytes)


# Context variable to store request-level passthrough headers for MCP
current_passthrough_headers: ContextVar[dict[str, str] | None] = ContextVar(
    "current_passthrough_headers",
    default=None,
)

# Context variables for explicit task progress updates
current_task_progress_tracker: ContextVar[Any | None] = ContextVar(
    "current_task_progress_tracker",
    default=None,
)
current_task_progress_chat_id: ContextVar[str | None] = ContextVar(
    "current_task_progress_chat_id",
    default=None,
)
current_task_progress_turn_id: ContextVar[str | None] = ContextVar(
    "current_task_progress_turn_id",
    default=None,
)


def get_current_passthrough_headers() -> dict[str, str] | None:
    """Get current passthrough headers from context.

    These headers are extracted from x-header-* HTTP headers and
    will be merged into MCP client HTTP requests.

    Returns:
        Dictionary of headers to passthrough, or None if not set.
    """
    return current_passthrough_headers.get()


def set_current_passthrough_headers(headers: dict[str, str] | None) -> Token:
    """Set current passthrough headers in context.

    Args:
        headers: Dictionary of headers to passthrough to MCP servers.

    Returns:
        Token for resetting the context variable.
    """
    return current_passthrough_headers.set(headers)


def reset_current_passthrough_headers(token: Token) -> None:
    """Reset passthrough headers using token.

    Args:
        token: The token returned by set_current_passthrough_headers.
    """
    current_passthrough_headers.reset(token)


def get_current_task_progress_tracker() -> Any | None:
    """Get current task progress tracker from context."""
    return current_task_progress_tracker.get()


def set_current_task_progress_tracker(tracker: Any | None) -> Token:
    """Set current task progress tracker in context."""
    return current_task_progress_tracker.set(tracker)


def reset_current_task_progress_tracker(token: Token) -> None:
    """Reset current task progress tracker using token."""
    current_task_progress_tracker.reset(token)


def get_current_task_progress_chat_id() -> str | None:
    """Get current task progress chat id from context."""
    return current_task_progress_chat_id.get()


def set_current_task_progress_chat_id(chat_id: str | None) -> Token:
    """Set current task progress chat id in context."""
    return current_task_progress_chat_id.set(chat_id)


def reset_current_task_progress_chat_id(token: Token) -> None:
    """Reset current task progress chat id using token."""
    current_task_progress_chat_id.reset(token)


def get_current_task_progress_turn_id() -> str | None:
    """Get current task progress turn id from context."""
    return current_task_progress_turn_id.get()


def set_current_task_progress_turn_id(turn_id: str | None) -> Token:
    """Set current task progress turn id in context."""
    return current_task_progress_turn_id.set(turn_id)


def reset_current_task_progress_turn_id(token: Token) -> None:
    """Reset current task progress turn id using token."""
    current_task_progress_turn_id.reset(token)


def resolve_effective_tenant_id(
    tenant_id: str,
    source_id: str | None,
) -> str:
    """兼容旧调用方的 runtime tenant 解析别名。

    新运行时统一使用编码后的 scope_id；保留该函数仅用于兼容历史导入，
    避免调用方通过旧名称重新引入 ``default_{source}`` 目录语义。
    """
    return resolve_runtime_tenant_id(tenant_id, source_id) or tenant_id
