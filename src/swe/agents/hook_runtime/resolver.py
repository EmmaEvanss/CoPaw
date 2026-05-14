# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from datetime import datetime, timezone
from typing import Any

from .models import (
    EffectiveHookHandler,
    EffectiveHookPlan,
    HookConfig,
    HookContext,
    HookHandlerConfig,
    HookMatcherGroupConfig,
    HookSessionOverlay,
    copy_handler_with_overrides,
)


class HookResolver:
    def __init__(
        self,
        *,
        tenant_config: HookConfig | None = None,
        agent_config: HookConfig | None = None,
        session_overlay: HookSessionOverlay | None = None,
        now: datetime | None = None,
    ) -> None:
        self.tenant_config = tenant_config or HookConfig()
        self.agent_config = agent_config or HookConfig()
        self.session_overlay = session_overlay or HookSessionOverlay()
        self.now = now or datetime.now(timezone.utc)

    def resolve_event_plan(self, context: HookContext) -> EffectiveHookPlan:
        loaded_skill_configs = [
            source.hook_config
            for source in self.session_overlay.loaded_skill_sources
            if source.hook_config.enabled
        ]
        if (
            not self.tenant_config.enabled
            and not self.agent_config.enabled
            and not loaded_skill_configs
        ):
            return EffectiveHookPlan(
                event_name=context.hook_event_name,
                context=context,
                handlers=(),
            )

        available_ids = (
            self.tenant_config.handler_ids() | self.agent_config.handler_ids()
        )
        for config in loaded_skill_configs:
            available_ids.update(config.handler_ids())
        overlay_entries = {
            entry.hook_id: entry
            for entry in self.session_overlay.entries
            if not entry.is_expired(self.now)
            and entry.hook_id in available_ids
        }

        handlers: list[EffectiveHookHandler] = []
        seen: set[str] = set()
        order = 0
        for config in (
            self.tenant_config,
            self.agent_config,
            *loaded_skill_configs,
        ):
            if not config.enabled:
                continue
            event_name = _event_name_value(context.hook_event_name)
            groups_by_event: dict[Any, list[HookMatcherGroupConfig]] = (
                config.events
            )
            groups = groups_by_event.get(context.hook_event_name, [])
            if not groups:
                groups = groups_by_event.get(event_name, [])
            for group_index, group in enumerate(groups):
                group_id = group.id or f"group-{group_index}"
                if not group.matcher.matches(context):
                    continue
                for raw_handler in group.hooks:
                    handler = self._apply_overlay(raw_handler, overlay_entries)
                    if handler is None:
                        continue
                    if not self._matches_if(handler.if_condition, context):
                        continue
                    if self._once_already_executed(handler, context):
                        continue
                    dedupe_key = self._dedupe_key(
                        context.effective_tenant_id,
                        event_name,
                        group_id,
                        handler,
                    )
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    handlers.append(
                        EffectiveHookHandler(
                            handler=handler,
                            group_id=group_id,
                            order=order,
                            dedupe_key=dedupe_key,
                        ),
                    )
                    order += 1

        return EffectiveHookPlan(
            event_name=context.hook_event_name,
            context=context,
            handlers=tuple(handlers),
        )

    def _apply_overlay(
        self,
        handler: HookHandlerConfig,
        entries: dict[str, Any],
    ) -> HookHandlerConfig | None:
        entry = entries.get(handler.id)
        if entry is None:
            return handler
        if entry.enabled is False:
            return None
        if entry.overrides:
            return copy_handler_with_overrides(handler, entry.overrides)
        return handler

    def _once_already_executed(
        self,
        handler: HookHandlerConfig,
        context: HookContext,
    ) -> bool:
        if not handler.once:
            return False
        return bool(
            self.session_overlay.once_executed.get(
                once_key(
                    context.effective_tenant_id,
                    context.user_id,
                    context.session_id,
                    _event_name_value(context.hook_event_name),
                    handler.id,
                ),
            ),
        )

    @staticmethod
    def _dedupe_key(
        tenant_id: str,
        event_name: str,
        group_id: str,
        handler: HookHandlerConfig,
    ) -> str:
        return (
            f"{tenant_id}:{event_name}:{group_id}:"
            f"{handler.id}:{handler.type}:{handler.target_identity()}"
        )

    @staticmethod
    def _matches_if(expression: str, context: HookContext) -> bool:
        if not expression:
            return True
        values = context.to_handler_payload()
        try:
            parsed = ast.parse(expression, mode="eval")
            return bool(_eval_if_node(parsed.body, values))
        except Exception:
            return False


def once_key(
    effective_tenant_id: str,
    user_id: str,
    session_id: str,
    event_name: str,
    handler_id: str,
) -> str:
    return (
        f"{effective_tenant_id}:{user_id}:{session_id}:"
        f"{event_name}:{handler_id}"
    )


def _event_name_value(event_name: Any) -> str:
    return str(getattr(event_name, "value", event_name))


def _eval_if_node(node: ast.AST, values: dict[str, Any]) -> Any:  # noqa: C901
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_if_node(node.operand, values)
    if isinstance(node, ast.BoolOp):
        items = [_eval_if_node(value, values) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(items)
        if isinstance(node.op, ast.Or):
            return any(items)
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and len(node.comparators) == 1
    ):
        left = _eval_if_node(node.left, values)
        right = _eval_if_node(node.comparators[0], values)
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
    if isinstance(node, ast.Attribute):
        base = _eval_if_node(node.value, values)
        if isinstance(base, dict):
            return base.get(node.attr)
    if isinstance(node, ast.Subscript):
        base = _eval_if_node(node.value, values)
        key = _eval_if_node(node.slice, values)
        if isinstance(base, dict):
            return base.get(key)
    if isinstance(node, ast.List):
        return [_eval_if_node(item, values) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_if_node(item, values) for item in node.elts)
    raise ValueError("unsupported hook if expression")
