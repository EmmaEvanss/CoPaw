# -*- coding: utf-8 -*-
"""BBK（机构）映射配置。

提供机构名称与 ID 之间的双向映射。
"""

from typing import Optional

# BBK 映射数组（与前端 bbk.ts 保持一致）
BBK_MAP = [
    {"label": "总行", "value": "100"},
    {"label": "北京分行", "value": "200"},
    {"label": "上海分行", "value": "201"},
    {"label": "深圳分行", "value": "202"},
    {"label": "广州分行", "value": "203"},
]

# 名称到 ID 的映射
_BBK_NAME_TO_ID: dict[str, str] = {
    item["label"]: item["value"] for item in BBK_MAP
}

# ID 到名称的映射
_BBK_ID_TO_NAME: dict[str, str] = {
    item["value"]: item["label"] for item in BBK_MAP
}

# 导出供外部使用
BBK_ID_TO_NAME_MAP = _BBK_ID_TO_NAME


def get_bbk_id_by_name(name: str) -> Optional[str]:
    """通过机构名称获取机构 ID。

    Args:
        name: 机构名称，如 "总行"

    Returns:
        机构 ID，如 "100"；未找到返回 None
    """
    return _BBK_NAME_TO_ID.get(name)


def get_bbk_name_by_id(bbk_id: str) -> Optional[str]:
    """通过机构 ID 获取机构名称。

    Args:
        bbk_id: 机构 ID，如 "100"

    Returns:
        机构名称，如 "总行"；未找到返回 None
    """
    return _BBK_ID_TO_NAME.get(bbk_id)
