# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from .models import (
    AdditionalContext,
    EffectiveHookPlan,
    HookDecision,
    HookHandlerResult,
    HookPermissionDecision,
    MergedHookResult,
)

_DECISION_PRIORITY = {
    HookDecision.NONE: 0,
    HookDecision.ALLOW: 1,
    HookDecision.ASK: 2,
    HookDecision.DENY: 3,
    HookDecision.BLOCK: 3,
    HookDecision.STOP: 4,
}


def _stronger(left: HookDecision, right: HookDecision) -> HookDecision:
    if _DECISION_PRIORITY[right] > _DECISION_PRIORITY[left]:
        return right
    return left


def merge_hook_results(  # noqa: C901
    plan: EffectiveHookPlan,
    results: Iterable[HookHandlerResult],
) -> MergedHookResult:
    by_order = sorted(results, key=lambda item: item.order)
    merged = MergedHookResult()
    updated_inputs: list[tuple[str, dict]] = []

    for result in by_order:
        specific = result.output.hook_specific_output or {}
        if specific:
            merged.hook_specific_outputs[result.handler_id] = dict(specific)

        permission_decision = specific.get("permissionDecision")
        if permission_decision in {"allow", "ask", "deny"}:
            merged.permission_decisions.append(
                HookPermissionDecision(
                    handler_id=result.handler_id,
                    decision=HookDecision(permission_decision),
                    reason=str(
                        specific.get("permissionDecisionReason")
                        or result.reason
                        or "",
                    ),
                ),
            )

        additional = specific.get("additionalContext")
        if additional:
            if isinstance(additional, list):
                for item in additional:
                    merged.additional_context.append(
                        AdditionalContext(
                            handler_id=result.handler_id,
                            context=str(item),
                        ),
                    )
            else:
                merged.additional_context.append(
                    AdditionalContext(
                        handler_id=result.handler_id,
                        context=str(additional),
                    ),
                )

        if specific.get("updatedInput") is not None:
            updated = specific["updatedInput"]
            if isinstance(updated, dict):
                updated_inputs.append((result.handler_id, updated))

        session_title = specific.get("sessionTitle")
        if session_title and merged.session_title is None:
            merged.session_title = str(session_title)

        if result.output.system_message:
            merged.system_messages.append(result.output.system_message)
        if result.output.suppress_output:
            merged.suppress_output = True

        next_decision = _stronger(merged.decision, result.decision)
        if next_decision != merged.decision:
            merged.decision = next_decision
            merged.reason = result.reason
        elif not merged.reason and result.reason:
            merged.reason = result.reason

    if len(updated_inputs) == 1:
        merged.updated_input = updated_inputs[0][1]
    elif len(updated_inputs) > 1:
        ids = ", ".join(handler_id for handler_id, _ in updated_inputs)
        merged.decision = HookDecision.BLOCK
        merged.reason = f"Multiple hooks returned updatedInput: {ids}"
        merged.updated_input = None

    if not plan.handlers and merged.decision == HookDecision.NONE:
        merged.reason = ""
    return merged
