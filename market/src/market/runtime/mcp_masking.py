# -*- coding: utf-8 -*-
"""MCP 敏感字段脱敏与回填辅助函数。"""

from __future__ import annotations


def mask_env_value(value: str) -> str:
    """按现有 SWE 规则对敏感值做可逆展示脱敏。"""
    if not value:
        return value

    length = len(value)
    if length <= 8:
        return "*" * length

    prefix_len = 3 if length > 2 and value[2] == "-" else 2
    prefix = value[:prefix_len]
    suffix = value[-4:]
    masked_len = max(length - prefix_len - 4, 4)
    return f"{prefix}{'*' * masked_len}{suffix}"


def restore_original_values(
    incoming: dict[str, str],
    existing: dict[str, str],
) -> dict[str, str]:
    """当传回的是脱敏值时，用旧值恢复真实内容。"""
    restored: dict[str, str] = {}
    for key, value in incoming.items():
        if key in existing and value == mask_env_value(existing[key]):
            restored[key] = existing[key]
        else:
            restored[key] = value
    return restored
