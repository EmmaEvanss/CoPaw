# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from pathlib import Path

from .executor import execute_handler
from .merge import merge_hook_results
from .models import (
    HookConfig,
    HookContext,
    HookSessionOverlay,
    MergedHookResult,
)
from .resolver import HookResolver, once_key


class HookRuntime:
    """Event-boundary resolver and concurrent handler executor."""

    def __init__(
        self,
        *,
        tenant_config: HookConfig | None = None,
        agent_config: HookConfig | None = None,
        session_overlay: HookSessionOverlay | None = None,
    ) -> None:
        self.tenant_config = tenant_config or HookConfig()
        self.agent_config = agent_config or HookConfig()
        self.session_overlay = session_overlay or HookSessionOverlay()

    async def emit(
        self,
        context: HookContext,
        *,
        workspace_dir: Path,
    ) -> MergedHookResult:
        plan = HookResolver(
            tenant_config=self.tenant_config,
            agent_config=self.agent_config,
            session_overlay=self.session_overlay,
        ).resolve_event_plan(context)
        if not plan.handlers:
            return merge_hook_results(plan, [])

        async def _run(item):
            result = await execute_handler(
                item.handler,
                context,
                workspace_dir=workspace_dir,
            )
            result.order = item.order
            return result

        results = await asyncio.gather(*(_run(item) for item in plan.handlers))
        self._mark_once_executed(context, plan.handlers)
        return merge_hook_results(plan, results)

    def _mark_once_executed(self, context: HookContext, handlers) -> None:
        for item in handlers:
            if not item.handler.once:
                continue
            self.session_overlay.once_executed[
                once_key(
                    context.effective_tenant_id,
                    context.user_id,
                    context.session_id,
                    str(
                        getattr(
                            context.hook_event_name,
                            "value",
                            context.hook_event_name,
                        ),
                    ),
                    item.handler.id,
                )
            ] = True
