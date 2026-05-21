# -*- coding: utf-8 -*-
"""Runner 模块导出入口。

这里避免在包导入阶段立刻加载 `runner.py`，否则像
`react_agent -> tools -> update_task_progress -> app.runner.task_progress`
这样的轻量子模块引用，也会被动触发 `AgentRunner` 导入并形成循环依赖。
"""

from __future__ import annotations

__all__ = [
    # Core classes
    "AgentRunner",
    "ChatManager",
    # API
    "router",
    # Models
    "ChatSpec",
    "ChatHistory",
    "ChatsFile",
    # Chat Repository
    "BaseChatRepository",
    "JsonChatRepository",
]


def __getattr__(name: str):
    if name == "AgentRunner":
        from .runner import AgentRunner as _AgentRunner

        return _AgentRunner
    if name == "router":
        from .api import router as _router

        return _router
    if name == "ChatManager":
        from .manager import ChatManager as _ChatManager

        return _ChatManager
    if name in {"ChatSpec", "ChatHistory", "ChatsFile"}:
        from .models import (
            ChatHistory as _ChatHistory,
            ChatsFile as _ChatsFile,
            ChatSpec as _ChatSpec,
        )

        exports = {
            "ChatSpec": _ChatSpec,
            "ChatHistory": _ChatHistory,
            "ChatsFile": _ChatsFile,
        }
        return exports[name]
    if name in {"BaseChatRepository", "JsonChatRepository"}:
        from .repo import (
            BaseChatRepository as _BaseChatRepository,
            JsonChatRepository as _JsonChatRepository,
        )

        exports = {
            "BaseChatRepository": _BaseChatRepository,
            "JsonChatRepository": _JsonChatRepository,
        }
        return exports[name]
    raise AttributeError(name)
