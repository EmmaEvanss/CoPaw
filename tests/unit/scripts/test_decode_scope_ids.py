# -*- coding: utf-8 -*-
"""scope 反解脚本的回归测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_script_module():
    """按文件路径加载脚本模块，避免依赖 scripts 成为包。"""
    script_path = (
        Path(__file__).resolve().parents[3] / "scripts" / "decode_scope_ids.py"
    )
    spec = importlib.util.spec_from_file_location(
        "decode_scope_ids",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_decode_scope_id_returns_logical_tenant_and_source() -> None:
    """canonical scope 应能反解为原始 tenant/source。"""
    module = _load_script_module()

    decoded = module.decode_canonical_scope_id("dGVuYW50LWE.c291cmNlLWE")

    assert decoded.scope_id == "dGVuYW50LWE.c291cmNlLWE"
    assert decoded.tenant_id == "tenant-a"
    assert decoded.source_id == "source-a"


def test_parse_scope_ids_supports_comma_separated_input() -> None:
    """批量参数应支持逗号分隔并忽略两侧空白。"""
    module = _load_script_module()

    assert module.parse_scope_ids(
        "dGVuYW50LWE.c291cmNlLWE, ZGVmYXVsdA.cnVpY2U",
    ) == (
        "dGVuYW50LWE.c291cmNlLWE",
        "ZGVmYXVsdA.cnVpY2U",
    )


def test_decode_scope_id_rejects_legacy_prefix() -> None:
    """脚本只支持 canonical scope，legacy 前缀必须拒绝。"""
    module = _load_script_module()

    with pytest.raises(ValueError):
        module.decode_canonical_scope_id(
            "scope.v1.dGVuYW50LWE.c291cmNlLWE",
        )
