# -*- coding: utf-8 -*-
"""Source 系统配置请求上下文。"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Generator

from swe.config.config import ToolResultCompactConfig

from .registry import normalize_registered_setting_values
from .models import EffectiveSourceSystemConfig

_current_source_system_config: ContextVar[
    EffectiveSourceSystemConfig | None
] = ContextVar("current_source_system_config", default=None)
logger = logging.getLogger(__name__)


@contextmanager
def bind_source_system_config(
    config: EffectiveSourceSystemConfig,
) -> Generator[None, None, None]:
    """在当前执行上下文绑定 source 系统配置。"""
    token = _current_source_system_config.set(config)
    try:
        yield
    finally:
        _current_source_system_config.reset(token)


def set_current_source_system_config(
    config: EffectiveSourceSystemConfig,
) -> Token[EffectiveSourceSystemConfig | None]:
    """设置当前 source 系统配置并返回 reset token。"""
    return _current_source_system_config.set(config)


def reset_current_source_system_config(
    token: Token[EffectiveSourceSystemConfig | None],
) -> None:
    """使用 token 还原当前 source 系统配置。"""
    _current_source_system_config.reset(token)


def get_current_source_system_config() -> EffectiveSourceSystemConfig | None:
    """读取当前上下文中的 source 系统配置。"""
    return _current_source_system_config.get()


def resolve_tool_result_compact_config(
    base_config: ToolResultCompactConfig,
    source_config: Any | None = None,
) -> ToolResultCompactConfig:
    """合成 Agent 运行配置和当前 source 的显式工具结果压缩覆盖。"""
    source_payload = _extract_tool_result_compact_override(source_config)
    if not source_payload:
        return base_config.model_copy(deep=True)

    payload = base_config.model_dump(mode="python")
    payload.update(source_payload)
    if payload["recent_max_bytes"] < payload["old_max_bytes"]:
        logger.warning(
            "Invalid source tool_result_compact thresholds resolved for "
            "source %s: recent_max_bytes=%s, old_max_bytes=%s; adjusted "
            "recent_max_bytes to old_max_bytes",
            _get_source_config_id(source_config),
            payload["recent_max_bytes"],
            payload["old_max_bytes"],
        )
        payload["recent_max_bytes"] = payload["old_max_bytes"]
    return ToolResultCompactConfig.model_validate(payload)


def _get_source_config_id(source_config: Any | None) -> str:
    """尽量提取 source 标识，日志缺少上下文时回退为 unknown。"""
    config = (
        get_current_source_system_config()
        if source_config is None
        else source_config
    )
    source_id = getattr(config, "source_id", None)
    if isinstance(source_id, str) and source_id:
        return source_id
    return "unknown"


def _extract_tool_result_compact_override(
    source_config: Any | None,
) -> dict[str, Any]:
    """只读取 raw source 配置，避免 registered default 覆盖 Agent 配置。"""
    config = (
        get_current_source_system_config()
        if source_config is None
        else source_config
    )
    if config is None:
        return {}
    raw_config = getattr(config, "raw_config", None)
    if raw_config is not None:
        return _extract_tool_result_compact_override(raw_config)
    if hasattr(config, "as_dict"):
        payload = config.as_dict()
    elif hasattr(config, "config") and not isinstance(config, dict):
        payload = getattr(config, "config")
        return _extract_tool_result_compact_override(payload)
    elif isinstance(config, dict):
        payload = config
    else:
        return {}

    tool_result_compact = payload.get("tool_result_compact")
    if not isinstance(tool_result_compact, dict):
        return {}
    normalized = normalize_registered_setting_values(
        {"tool_result_compact": tool_result_compact},
    )
    normalized_tool_result = normalized.get("tool_result_compact")
    if not isinstance(normalized_tool_result, dict):
        return {}
    return normalized_tool_result
