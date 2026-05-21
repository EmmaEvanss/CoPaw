# -*- coding: utf-8 -*-
"""Source 系统配置请求上下文。"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generator

from .models import EffectiveSourceSystemConfig

_current_source_system_config: ContextVar[
    EffectiveSourceSystemConfig | None
] = ContextVar("current_source_system_config", default=None)


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
