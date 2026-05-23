# -*- coding: utf-8 -*-
"""MCP HTTP header 解析工具。"""

from __future__ import annotations

import os
from typing import Mapping

from swe.envs.runtime import resolve_tenant_env_references_mapping


def resolve_mcp_http_headers(
    headers: Mapping[str, str] | None,
) -> dict[str, str] | None:
    """先展开进程 env，再解析 tenant env 引用，避免 secret 被二次展开。"""
    if not headers:
        return None

    expanded_headers = {
        key: os.path.expandvars(value) for key, value in headers.items()
    }
    return resolve_tenant_env_references_mapping(expanded_headers)
