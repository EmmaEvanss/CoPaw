# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

from json_repair import loads as repair_json_loads

from .models import HookDecision, HookHandlerResult, HookOutput

PROMPT_JUDGMENT_MAX_REASON_LENGTH = 2000
_PROMPT_JUDGMENT_KEYS = {"decision", "reason"}
_PROMPT_JUDGMENT_DECISIONS = {
    "allow": HookDecision.ALLOW,
    "deny": HookDecision.DENY,
    "block": HookDecision.BLOCK,
}


def _parse_prompt_judgment_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as original_exc:
        try:
            return repair_json_loads(text, skip_json_loads=True)
        except ValueError as repair_exc:
            raise ValueError(
                f"Invalid prompt hook JSON output: {original_exc}",
            ) from repair_exc


def normalize_hook_output(
    *,
    handler_id: str,
    order: int,
    raw_output: dict[str, Any],
) -> HookHandlerResult:
    output = HookOutput.model_validate(raw_output)
    decision = HookDecision.NONE
    reason = output.reason or ""

    if output.continue_ is False:
        decision = HookDecision.STOP
        reason = output.stop_reason or reason or "Hook requested stop"
    elif output.decision == "block":
        decision = HookDecision.BLOCK
        reason = reason or "Hook blocked the event"

    specific = output.hook_specific_output or {}
    permission_decision = specific.get("permissionDecision")
    permission_reason = specific.get("permissionDecisionReason")
    if permission_decision in {"allow", "deny", "ask"}:
        decision = HookDecision(permission_decision)
        reason = str(permission_reason or reason or "")
    elif permission_decision == "defer":
        decision = HookDecision.BLOCK
        reason = "Hook permissionDecision=defer is not supported"

    return HookHandlerResult(
        handler_id=handler_id,
        order=order,
        output=output,
        decision=decision,
        reason=reason,
    )


def normalize_prompt_judgment_output(
    *,
    handler_id: str,
    order: int,
    text: str,
) -> HookHandlerResult:
    raw = _parse_prompt_judgment_json(text)
    if not isinstance(raw, dict):
        raise ValueError("Prompt hook output must be a JSON object")
    if set(raw) != _PROMPT_JUDGMENT_KEYS:
        raise ValueError(
            "Prompt hook output must contain exactly decision and reason",
        )

    decision_value = raw.get("decision")
    if decision_value not in _PROMPT_JUDGMENT_DECISIONS:
        raise ValueError("Prompt hook output has unsupported decision")

    reason = raw.get("reason")
    if not isinstance(reason, str):
        raise ValueError("Prompt hook output reason must be a string")
    reason = reason.strip()
    if not reason:
        raise ValueError("Prompt hook output reason must be non-empty")
    if len(reason) > PROMPT_JUDGMENT_MAX_REASON_LENGTH:
        raise ValueError("Prompt hook output reason is too long")

    output = HookOutput(decision=decision_value, reason=reason)
    return HookHandlerResult(
        handler_id=handler_id,
        order=order,
        output=output,
        decision=_PROMPT_JUDGMENT_DECISIONS[decision_value],
        reason=reason,
    )
