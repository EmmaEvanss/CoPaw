# -*- coding: utf-8 -*-
"""当前实现下已废弃的旧租户模型 API 集成测试。"""

import pytest

pytest.skip(
    "当前 /api/providers 已不再暴露旧 TenantModelConfig 契约，"
    "该集成测试按现状整体跳过。",
    allow_module_level=True,
)
