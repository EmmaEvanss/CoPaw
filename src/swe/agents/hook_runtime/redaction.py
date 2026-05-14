# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "headers",
}


def redact_hook_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(sensitive in key_text for sensitive in SENSITIVE_KEYS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_hook_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_hook_payload(item) for item in value]
    return value
