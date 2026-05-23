# -*- coding: utf-8 -*-
"""Tracing 数据脱敏工具。"""

from contextvars import ContextVar
from typing import Any, Optional

# Sensitive keys to redact from tool input/output
SENSITIVE_KEYS = frozenset(
    [
        "api_key",
        "apikey",
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "credential",
        "private_key",
        "access_token",
        "refresh_token",
        "session_id",
        "auth",
        "private-key",
        "privatekey",
        "secret_key",
        "secretkey",
        "api_secret",
        "apisecret",
    ],
)

_runtime_secret_values: ContextVar[tuple[str, ...]] = ContextVar(
    "runtime_secret_values",
    default=(),
)


def register_sensitive_values(values: Any) -> None:
    """登记当前上下文需要按值脱敏的 secret。"""
    existing = list(_runtime_secret_values.get())
    for value in values or ():
        if not isinstance(value, str) or not value:
            continue
        if value not in existing:
            existing.append(value)
    _runtime_secret_values.set(tuple(existing))


def _redact_registered_values(text: str) -> str:
    """按当前上下文登记的 secret 值执行最小替换。"""
    redacted = text
    for secret in _runtime_secret_values.get():
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def sanitize_dict(
    data: Optional[dict[str, Any]],
    max_length: int = 500,
) -> Optional[dict]:
    """按 key 和已登记 secret 值清理字典。"""
    if data is None:
        return None

    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        # Check if key contains any sensitive keyword
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = sanitize_string(value, max_length)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, max_length)
        elif isinstance(value, list):
            result[key] = [
                (
                    sanitize_dict(item, max_length)
                    if isinstance(item, dict)
                    else (
                        sanitize_string(item, max_length)
                        if isinstance(item, str)
                        else item
                    )
                )
                for item in value
            ]
        else:
            result[key] = value
    return result


def sanitize_string(
    text: Optional[str],
    max_length: int = 500,
) -> Optional[str]:
    """截断字符串，并替换当前上下文已登记的 secret 值。"""
    if text is None:
        return None
    text = _redact_registered_values(text)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def sanitize_user_message(
    message: Optional[str],
    max_length: int = 500,
) -> Optional[str]:
    """清理用户消息后再落入 tracing。"""
    return sanitize_string(message, max_length)
