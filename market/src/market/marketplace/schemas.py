# -*- coding: utf-8 -*-
"""API 请求/响应模型."""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class PublishSkillRequest(BaseModel):
    """上架技能请求体."""

    name: str
    description: str = ""
    creator_id: str
    creator_name: str = ""
    category_id: Optional[int] = None
    bbk_ids: list[str] = Field(default_factory=list)
    skill_json: dict = Field(default_factory=dict)
    skill_md: str = ""


class DistributeRequest(BaseModel):
    """分发技能请求体."""

    target_type: Literal["all", "bbk_id", "user_id"]
    target_values: list[str] = Field(default_factory=list)


class MarketSkillResponse(BaseModel):
    """市场技能列表/详情响应."""

    item_id: str
    name: str
    description: str
    version: str
    creator_id: str
    creator_name: str
    category_id: Optional[int]
    bbk_ids: list[str]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]
    call_count: int = 0
    user_count: int = 0


class SkillUserStat(BaseModel):
    """技能详情页调用客户明细."""

    user_id: str
    user_name: str
    call_count: int


class MarketSkillDetail(MarketSkillResponse):
    """技能详情（含调用客户明细）."""

    user_stats: list[SkillUserStat] = Field(default_factory=list)


class MySkillItem(BaseModel):
    """我的技能列表条目."""

    skill_name: str
    source: str
    description: str = ""
    version: Optional[str] = None
    received_version: Optional[str] = None
    distributed_by: Optional[str] = None
    is_received: bool = False
    has_update: bool = False
    enabled: bool = True


class BatchOperationRequest(BaseModel):
    """批量操作请求."""

    skills: list[str]


class SkillOperationResult(BaseModel):
    """单个技能操作结果."""

    skill_name: str
    success: bool
    reason: str | None = None


class BatchOperationResponse(BaseModel):
    """批量操作响应."""

    results: dict[str, Any]
    success_count: int
    failed_count: int


class DistributeResponse(BaseModel):
    """分发结果."""

    distributed_count: int
    item_id: str


class FileTreeNode(BaseModel):
    """文件树节点."""

    name: str
    type: Literal["file", "directory"]
    path: str
    children: list["FileTreeNode"] | None = None


class FileContentResponse(BaseModel):
    """文件内容响应."""

    content: str
    file_type: str  # "markdown" | "json" | "text" | "binary"


class OperationResponse(BaseModel):
    """操作结果响应."""

    success: bool = True
    message: str | None = None


class UploadSkillResponse(BaseModel):
    """技能上传响应."""

    imported: list[str] = Field(default_factory=list)
    count: int = 0
    enabled: bool = True
    name: str | None = None
    description: str | None = None
    conflicts: list[dict] | None = None
