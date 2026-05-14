# -*- coding: utf-8 -*-
from __future__ import annotations

from swe.agents.hook_runtime.redaction import redact_hook_payload


def test_redacts_hook_secrets_headers_and_sensitive_fields() -> None:
    payload = {
        "headers": {"Authorization": "Bearer token"},
        "tool_input": {
            "api_key": "secret-key",
            "safe": "value",
        },
        "nested": [{"password": "pw"}],
    }

    assert redact_hook_payload(payload) == {
        "headers": "[REDACTED]",
        "tool_input": {
            "api_key": "[REDACTED]",
            "safe": "value",
        },
        "nested": [{"password": "[REDACTED]"}],
    }
