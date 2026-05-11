# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

from datetime import datetime, timezone
from typing import Any, List, Optional

import segno

from fastapi import APIRouter, Body, HTTPException, Path, Request
from pydantic import BaseModel, Field

from ..utils import schedule_agent_reload
from ...config import (
    load_config,
    save_config,
    ChannelConfig,
    ChannelConfigUnion,
    get_available_channels,
    ToolGuardConfig,
    ToolGuardRuleConfig,
)
from ..channels.registry import BUILTIN_CHANNEL_KEYS
from ...config.config import (
    AgentsLLMRoutingConfig,
    ConsoleConfig,
    HeartbeatConfig,
    SkillScannerConfig,
    SkillScannerWhitelistEntry,
    ZhaohuConfig,
)

from .schemas_config import HeartbeatBody

router = APIRouter(prefix="/config", tags=["config"])


class ChannelDistributionRequest(BaseModel):
    """通道配置分发请求体。"""

    target_tenant_ids: List[str] = Field(
        default_factory=list,
        description="目标租户 ID 列表",
    )
    fields: Optional[List[str]] = Field(
        default=None,
        description="指定分发的字段列表，为 None 时分发全部字段",
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖目标租户已有值",
    )


class ChannelDistributionTenantResult(BaseModel):
    """单个租户的通道配置分发结果。"""

    tenant_id: str = Field(..., description="目标租户 ID")
    success: bool = Field(..., description="是否分发成功")
    bootstrapped: bool = Field(
        default=False,
        description="目标租户是否在分发过程中完成初始化",
    )
    error: str = Field(default="", description="失败原因")


class ChannelDistributionResponse(BaseModel):
    """通道配置分发响应。"""

    source_agent_id: str = Field(..., description="源 Agent ID")
    results: List[ChannelDistributionTenantResult] = Field(
        default_factory=list,
        description="各目标租户的分发结果",
    )


def _validate_target_tenant_id(tenant_id: str) -> str:
    """校验目标租户 ID 格式，防止路径穿越等注入。"""
    tenant_id = str(tenant_id or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required")
    if len(tenant_id) > 256:
        raise ValueError(f"Invalid tenant ID format: {tenant_id}")
    if ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
        raise ValueError(f"Invalid tenant ID format: {tenant_id}")
    if any(ord(c) < 32 for c in tenant_id):
        raise ValueError(f"Invalid tenant ID format: {tenant_id}")
    return tenant_id


_CHANNEL_CONFIG_CLASS_MAP = {
    "console": ConsoleConfig,
    "zhaohu": ZhaohuConfig,
}


@router.get(
    "/channels",
    summary="List all channels",
    description="Retrieve configuration for all available channels",
)
async def list_channels(request: Request) -> dict:
    """List all channel configs (filtered by available channels)."""
    from ..agent_context import get_agent_and_config_for_request

    _, agent_config = await get_agent_and_config_for_request(request)
    available = get_available_channels()

    # Get channel configs from agent's config (with fallback to empty)
    channels_config = agent_config.channels
    if channels_config is None:
        # No channels config yet, use empty defaults
        all_configs = {}
    else:
        all_configs = channels_config.model_dump()
        extra = getattr(channels_config, "__pydantic_extra__", None) or {}
        all_configs.update(extra)

    # Return all available channels (use default config if not saved)
    result = {}
    for key in available:
        if key in all_configs:
            channel_data = (
                dict(all_configs[key])
                if isinstance(all_configs[key], dict)
                else all_configs[key]
            )
        else:
            # Channel registered but no config saved yet, use empty default
            channel_data = {"enabled": False, "bot_prefix": ""}
        if isinstance(channel_data, dict):
            channel_data["isBuiltin"] = key in BUILTIN_CHANNEL_KEYS
        result[key] = channel_data

    return result


@router.get(
    "/channels/types",
    summary="List channel types",
    description="Return all available channel type identifiers",
)
async def list_channel_types() -> List[str]:
    """Return available channel type identifiers (env-filtered)."""
    return list(get_available_channels())


@router.put(
    "/channels",
    response_model=ChannelConfig,
    summary="Update all channels",
    description="Update configuration for all channels at once",
)
async def put_channels(
    request: Request,
    channels_config: ChannelConfig = Body(
        ...,
        description="Complete channel configuration",
    ),
) -> ChannelConfig:
    """Update all channel configs."""
    from ..agent_context import get_agent_and_config_for_request
    from ...config.config import save_agent_config

    agent, agent_config = await get_agent_and_config_for_request(request)
    agent_config.channels = channels_config
    save_agent_config(
        agent.agent_id,
        agent_config,
        tenant_id=agent.tenant_id,
    )

    # Hot reload config (async, non-blocking)
    schedule_agent_reload(
        request,
        agent.agent_id,
        tenant_id=agent.tenant_id,
    )

    return channels_config


async def _get_weixin_base_url(request: Request) -> str:
    """Return configured WeChat base_url for the current agent."""
    from ..channels.weixin.client import _DEFAULT_BASE_URL

    try:
        from ..agent_context import get_agent_and_config_for_request

        _, agent_config = await get_agent_and_config_for_request(request)
        channels = agent_config.channels
        if channels is not None:
            weixin_cfg = getattr(channels, "weixin", None)
            if weixin_cfg is not None:
                return getattr(weixin_cfg, "base_url", "") or _DEFAULT_BASE_URL
    except Exception:
        pass
    return _DEFAULT_BASE_URL


@router.get(
    "/channels/weixin/qrcode",
    summary="Get WeChat iLink login QR code",
    description="Fetch QR code image (base64 PNG) for WeChat iLink Bot login.",
)
async def get_weixin_qrcode(request: Request) -> dict:
    """Return a QR code image (base64 PNG) for WeChat iLink Bot login."""
    import base64
    import io
    import httpx
    from ..channels.weixin.client import ILinkClient

    base_url = await _get_weixin_base_url(request)
    client = ILinkClient(base_url=base_url)
    await client.start()
    try:
        qr_data = await client.get_bot_qrcode()
    except (httpx.HTTPError, Exception) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"WeChat QR code fetch failed: {exc}",
        ) from exc
    finally:
        await client.stop()

    qrcode = qr_data.get("qrcode", "")
    qrcode_img_url = qr_data.get("qrcode_img_content", "")

    if not qrcode and not qrcode_img_url:
        raise HTTPException(
            status_code=502,
            detail="WeChat returned empty QR code data",
        )

    # Generate QR code image from the scan URL using segno (pure Python)
    # The scan target is the URL that WeChat app should open when scanning
    if qrcode_img_url.startswith("http"):
        scan_url = qrcode_img_url
    else:
        scan_url = (
            f"https://liteapp.weixin.qq.com/q/7GiQu1"
            f"?qrcode={qrcode}&bot_type=3"
        )
    try:
        qr = segno.make(scan_url, error="M")
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=6, border=2)
        qrcode_img_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"QR code image generation failed: {exc}",
        ) from exc

    return {"qrcode_img": qrcode_img_b64, "qrcode": qrcode}


@router.get(
    "/channels/weixin/qrcode/status",
    summary="Poll WeChat iLink QR code scan status",
)
async def get_weixin_qrcode_status(
    request: Request,
    qrcode: str,
) -> dict:
    """Poll QR code scan status. Returns {status, bot_token, base_url}."""
    import httpx
    from ..channels.weixin.client import ILinkClient

    base_url = await _get_weixin_base_url(request)
    client = ILinkClient(base_url=base_url)
    await client.start()
    try:
        data = await client.get_qrcode_status(qrcode)
    except (httpx.HTTPError, Exception) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"WeChat status check failed: {exc}",
        ) from exc
    finally:
        await client.stop()

    return {
        "status": data.get("status", "waiting"),
        "bot_token": data.get("bot_token", ""),
        "base_url": data.get("baseurl", ""),
    }


@router.get(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Get channel config",
    description="Retrieve configuration for a specific channel by name",
)
async def get_channel(
    request: Request,
    channel_name: str = Path(
        ...,
        description="Name of the channel to retrieve",
        min_length=1,
    ),
) -> ChannelConfigUnion:
    """Get a specific channel config by name."""
    from ..agent_context import get_agent_and_config_for_request

    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )

    _, agent_config = await get_agent_and_config_for_request(request)
    channels = agent_config.channels
    if channels is None:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not configured",
        )

    single_channel_config = getattr(channels, channel_name, None)
    if single_channel_config is None:
        extra = getattr(channels, "__pydantic_extra__", None) or {}
        single_channel_config = extra.get(channel_name)
    if single_channel_config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    return single_channel_config


@router.put(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Update channel config",
    description="Update configuration for a specific channel by name",
)
async def put_channel(
    request: Request,
    channel_name: str = Path(
        ...,
        description="Name of the channel to update",
        min_length=1,
    ),
    single_channel_config: dict = Body(
        ...,
        description="Updated channel configuration",
    ),
) -> ChannelConfigUnion:
    """Update a specific channel config by name."""
    from ..agent_context import get_agent_and_config_for_request
    from ...config.config import save_agent_config

    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )

    agent, agent_config = await get_agent_and_config_for_request(request)

    # Initialize channels if not exists
    if agent_config.channels is None:
        agent_config.channels = ChannelConfig()

    config_class = _CHANNEL_CONFIG_CLASS_MAP.get(channel_name)
    if config_class is not None:
        channel_config = config_class(**single_channel_config)
    else:
        # For custom channels, just use the dict
        channel_config = single_channel_config

    # Set channel config in agent's config
    setattr(agent_config.channels, channel_name, channel_config)
    save_agent_config(
        agent.agent_id,
        agent_config,
        tenant_id=agent.tenant_id,
    )

    # Hot reload config (async, non-blocking)
    schedule_agent_reload(
        request,
        agent.agent_id,
        tenant_id=agent.tenant_id,
    )

    return channel_config


def _request_source_id(request: Request) -> str | None:
    return getattr(request.state, "source_id", None)


def _request_tenant_id(request: Request) -> str | None:
    return getattr(request.state, "tenant_id", None)


def _get_multi_agent_manager(request: Request):
    manager = getattr(request.app.state, "multi_agent_manager", None)
    if manager is None:
        raise RuntimeError("MultiAgentManager not initialized")
    return manager


def _extract_source_channel_config(source_channels, channel_name: str):
    source_channel = getattr(source_channels, channel_name, None)
    if source_channel is not None:
        return source_channel
    extra = getattr(source_channels, "__pydantic_extra__", None) or {}
    return extra.get(channel_name)


def _build_fields_to_distribute(
    source_channel,
    fields: Optional[List[str]],
) -> dict:
    source_dump = (
        source_channel.model_dump()
        if hasattr(source_channel, "model_dump")
        else dict(source_channel)
    )
    if fields:
        return {k: v for k, v in source_dump.items() if k in fields}
    return source_dump


def _merge_config_values(
    existing_values: dict,
    fields_to_distribute: dict,
    overwrite: bool,
) -> dict:
    merged_values = dict(existing_values)
    if overwrite:
        merged_values.update(fields_to_distribute)
        return merged_values
    for key, value in fields_to_distribute.items():
        if key not in merged_values or not merged_values[key]:
            merged_values[key] = value
    return merged_values


def _apply_distributed_channel_values(
    target_channels: ChannelConfig,
    channel_name: str,
    fields_to_distribute: dict,
    overwrite: bool,
) -> None:
    config_class = _CHANNEL_CONFIG_CLASS_MAP.get(channel_name)
    existing = getattr(target_channels, channel_name, None)

    if config_class is not None:
        if existing is not None:
            merged = _merge_config_values(
                existing.model_dump(),
                fields_to_distribute,
                overwrite,
            )
            setattr(target_channels, channel_name, config_class(**merged))
            return
        setattr(
            target_channels,
            channel_name,
            config_class(**fields_to_distribute),
        )
        return

    if existing is not None and isinstance(existing, dict):
        merged_dict = _merge_config_values(
            existing,
            fields_to_distribute,
            overwrite,
        )
        setattr(target_channels, channel_name, merged_dict)
        return

    setattr(target_channels, channel_name, fields_to_distribute)


def _prepare_target_tenant(
    request: Request,
    tenant_id: str,
):
    from ...config.context import resolve_effective_tenant_id
    from ...config.utils import get_tenant_working_dir_strict
    from ..workspace.tenant_initializer import TenantInitializer

    validated_tenant_id = _validate_target_tenant_id(tenant_id)
    effective_tid = resolve_effective_tenant_id(
        validated_tenant_id,
        _request_source_id(request),
    )
    tenant_working_dir = get_tenant_working_dir_strict(effective_tid)
    initializer = TenantInitializer(
        tenant_working_dir.parent,
        validated_tenant_id,
        source_id=_request_source_id(request),
    )
    was_bootstrapped = initializer.has_seeded_bootstrap()
    if not was_bootstrapped:
        initializer.ensure_seeded_bootstrap()

    effective_target_tenant_id = getattr(
        initializer,
        "effective_tenant_id",
        validated_tenant_id,
    )
    return validated_tenant_id, effective_target_tenant_id, was_bootstrapped


@router.get(
    "/channels/distribution/tenants",
    summary="列出可分发通道配置的目标租户",
)
async def list_channel_distribution_tenants(
    request: Request,
) -> dict:
    """返回当前 source 下的所有租户 ID 列表，供通道配置分发选择。"""
    from ...config.utils import list_logical_tenant_ids

    tenant_ids = await list_logical_tenant_ids(
        _request_source_id(request),
        source_filter=True,
    )
    return {"tenant_ids": tenant_ids}


@router.post(
    "/channels/{channel_name}/distribute",
    response_model=ChannelDistributionResponse,
    summary="将通道配置分发到目标租户",
)
async def distribute_channel_config(
    request: Request,
    channel_name: str = Path(..., description="通道名称", min_length=1),
    body: ChannelDistributionRequest = Body(...),
) -> ChannelDistributionResponse:
    """从源租户读取通道配置，按字段级分发到目标租户的 default agent。

    非覆盖模式下仅填充目标租户中为空或不存在的字段。
    """
    from ..agent_context import get_agent_for_request
    from ...config.config import load_agent_config, save_agent_config

    if not body.target_tenant_ids:
        raise HTTPException(
            status_code=400,
            detail="No target tenant IDs provided",
        )

    # fields 为空列表时无意义，直接返回
    if body.fields is not None and len(body.fields) == 0:
        return ChannelDistributionResponse(
            source_agent_id="",
            results=[],
        )

    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )

    # 加载源租户通道配置
    source_agent = await get_agent_for_request(request)
    source_config = load_agent_config(
        source_agent.agent_id,
        tenant_id=source_agent.tenant_id,
    )
    source_channels = source_config.channels
    if source_channels is None:
        raise HTTPException(
            status_code=400,
            detail="Source agent has no channel config",
        )
    source_channel = _extract_source_channel_config(
        source_channels,
        channel_name,
    )
    if source_channel is None:
        raise HTTPException(
            status_code=400,
            detail=f"Source agent has no '{channel_name}' channel config",
        )

    # 确定要分发的字段（fields 仅控制"分发哪些字段"）
    fields_to_distribute = _build_fields_to_distribute(
        source_channel,
        body.fields,
    )

    # 去重并排除源租户自身
    source_tenant_id = source_agent.tenant_id
    unique_tenant_ids = list(dict.fromkeys(body.target_tenant_ids))
    target_tenant_ids = [
        tid for tid in unique_tenant_ids if tid != source_tenant_id
    ]

    results: List[ChannelDistributionTenantResult] = []

    for tenant_id in target_tenant_ids:
        try:
            (
                validated_tenant_id,
                effective_target_tenant_id,
                was_bootstrapped,
            ) = _prepare_target_tenant(request, tenant_id)

            target_config = load_agent_config(
                "default",
                tenant_id=effective_target_tenant_id,
            )
            original_target_config = target_config.model_copy(deep=True)

            if target_config.channels is None:
                target_config.channels = ChannelConfig()

            _apply_distributed_channel_values(
                target_config.channels,
                channel_name,
                fields_to_distribute,
                body.overwrite,
            )

            try:
                save_agent_config(
                    "default",
                    target_config,
                    tenant_id=effective_target_tenant_id,
                )
                schedule_agent_reload(
                    request,
                    "default",
                    tenant_id=effective_target_tenant_id,
                )
            except Exception:
                try:
                    save_agent_config(
                        "default",
                        original_target_config,
                        tenant_id=effective_target_tenant_id,
                    )
                except Exception:
                    pass
                schedule_agent_reload(
                    request,
                    "default",
                    tenant_id=effective_target_tenant_id,
                )
                raise

            results.append(
                ChannelDistributionTenantResult(
                    tenant_id=validated_tenant_id,
                    success=True,
                    bootstrapped=not was_bootstrapped,
                ),
            )
        except Exception as exc:
            results.append(
                ChannelDistributionTenantResult(
                    tenant_id=str(tenant_id),
                    success=False,
                    error=str(exc),
                ),
            )

    return ChannelDistributionResponse(
        source_agent_id=source_agent.agent_id,
        results=results,
    )


@router.get(
    "/heartbeat",
    summary="Get heartbeat config",
    description="Return current heartbeat config (interval, target, etc.)",
)
async def get_heartbeat(request: Request) -> Any:
    """Return effective heartbeat config (from file or default)."""
    from ..agent_context import get_agent_and_config_for_request
    from ...config.config import HeartbeatConfig as HeartbeatConfigModel

    _, agent_config = await get_agent_and_config_for_request(request)
    hb = agent_config.heartbeat
    if hb is None:
        # Use default if not configured
        hb = HeartbeatConfigModel()
    return hb.model_dump(mode="json", by_alias=True)


@router.put(
    "/heartbeat",
    summary="Update heartbeat config",
    description="Update heartbeat and hot-reload the scheduler",
)
async def put_heartbeat(
    request: Request,
    body: HeartbeatBody = Body(..., description="Heartbeat configuration"),
) -> Any:
    """Update heartbeat config and reschedule the heartbeat job."""
    from ..agent_context import get_agent_and_config_for_request
    from ...config.config import save_agent_config

    agent, agent_config = await get_agent_and_config_for_request(request)
    hb = HeartbeatConfig(
        enabled=body.enabled,
        every=body.every,
        target=body.target,
        active_hours=body.active_hours,
    )
    agent_config.heartbeat = hb
    save_agent_config(
        agent.agent_id,
        agent_config,
        tenant_id=agent.tenant_id,
    )

    # Reschedule heartbeat (async, non-blocking)
    import asyncio

    async def reschedule_in_background():
        try:
            if agent.cron_manager is not None:
                await agent.cron_manager.reschedule_heartbeat()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                f"Background reschedule failed: {e}",
            )

    asyncio.create_task(reschedule_in_background())

    return hb.model_dump(mode="json", by_alias=True)


@router.get(
    "/agents/llm-routing",
    response_model=AgentsLLMRoutingConfig,
    summary="Get agent LLM routing settings",
)
async def get_agents_llm_routing() -> AgentsLLMRoutingConfig:
    config = load_config()
    return config.agents.llm_routing


@router.put(
    "/agents/llm-routing",
    response_model=AgentsLLMRoutingConfig,
    summary="Update agent LLM routing settings",
)
async def put_agents_llm_routing(
    body: AgentsLLMRoutingConfig = Body(...),
) -> AgentsLLMRoutingConfig:
    config = load_config()
    config.agents.llm_routing = body
    save_config(config)
    return body


# ── User Timezone ────────────────────────────────────────────────────


@router.get(
    "/user-timezone",
    summary="Get user timezone",
    description="Return the configured user IANA timezone",
)
async def get_user_timezone() -> dict:
    config = load_config()
    return {"timezone": config.user_timezone}


@router.put(
    "/user-timezone",
    summary="Update user timezone",
    description="Set the user IANA timezone",
)
async def put_user_timezone(
    body: dict = Body(..., description="Body with 'timezone' key"),
) -> dict:
    tz = body.get("timezone", "").strip()
    if not tz:
        raise HTTPException(status_code=400, detail="timezone is required")
    config = load_config()
    config.user_timezone = tz
    save_config(config)
    return {"timezone": tz}


# ── Security / Tool Guard ────────────────────────────────────────────


@router.get(
    "/security/tool-guard",
    response_model=ToolGuardConfig,
    summary="Get tool guard settings",
)
async def get_tool_guard() -> ToolGuardConfig:
    config = load_config()
    return config.security.tool_guard


@router.put(
    "/security/tool-guard",
    response_model=ToolGuardConfig,
    summary="Update tool guard settings",
)
async def put_tool_guard(
    body: ToolGuardConfig = Body(...),
) -> ToolGuardConfig:
    config = load_config()
    config.security.tool_guard = body
    save_config(config)

    from ...security.tool_guard.engine import get_guard_engine

    engine = get_guard_engine()
    engine.enabled = body.enabled
    engine.reload_rules()

    return body


@router.get(
    "/security/tool-guard/builtin-rules",
    response_model=List[ToolGuardRuleConfig],
    summary="List built-in guard rules from YAML files",
)
async def get_builtin_rules() -> List[ToolGuardRuleConfig]:
    from ...security.tool_guard.guardians.rule_guardian import (
        load_rules_from_directory,
    )

    rules = load_rules_from_directory()
    return [
        ToolGuardRuleConfig(
            id=r.id,
            tools=r.tools,
            params=r.params,
            category=r.category.value,
            severity=r.severity.value,
            patterns=r.patterns,
            exclude_patterns=r.exclude_patterns,
            description=r.description,
            remediation=r.remediation,
        )
        for r in rules
    ]


# ── Security / File Guard ────────────────────────────────────────────


class FileGuardResponse(BaseModel):
    enabled: bool = True
    paths: List[str] = []


class FileGuardUpdateBody(BaseModel):
    enabled: Optional[bool] = None
    paths: Optional[List[str]] = None


@router.get(
    "/security/file-guard",
    response_model=FileGuardResponse,
    summary="Get file guard settings",
)
async def get_file_guard() -> FileGuardResponse:
    config = load_config()
    fg = config.security.file_guard
    paths = fg.sensitive_files
    if not paths:
        from ...security.tool_guard.guardians.file_guardian import (
            _DEFAULT_DENY_DIRS,
        )

        paths = list(_DEFAULT_DENY_DIRS)
    return FileGuardResponse(enabled=fg.enabled, paths=paths)


@router.put(
    "/security/file-guard",
    response_model=FileGuardResponse,
    summary="Update file guard settings",
)
async def put_file_guard(
    body: FileGuardUpdateBody,
) -> FileGuardResponse:
    config = load_config()
    fg = config.security.file_guard

    if body.enabled is not None:
        fg.enabled = body.enabled
    if body.paths is not None:
        fg.sensitive_files = body.paths

    save_config(config)

    from ...security.tool_guard.engine import get_guard_engine

    engine = get_guard_engine()
    engine.reload_rules()

    return FileGuardResponse(
        enabled=fg.enabled,
        paths=fg.sensitive_files,
    )


# ── Security / Skill Scanner ────────────────────────────────────────


@router.get(
    "/security/skill-scanner",
    response_model=SkillScannerConfig,
    summary="Get skill scanner settings",
)
async def get_skill_scanner() -> SkillScannerConfig:
    config = load_config()
    return config.security.skill_scanner


@router.put(
    "/security/skill-scanner",
    response_model=SkillScannerConfig,
    summary="Update skill scanner settings",
)
async def put_skill_scanner(
    body: SkillScannerConfig = Body(...),
) -> SkillScannerConfig:
    config = load_config()
    config.security.skill_scanner = body
    save_config(config)
    return body


@router.get(
    "/security/skill-scanner/blocked-history",
    summary="Get blocked skills history",
)
async def get_blocked_history() -> list:
    from ...security.skill_scanner import get_blocked_history as _get_history

    records = _get_history()
    return [r.to_dict() for r in records]


@router.delete(
    "/security/skill-scanner/blocked-history",
    summary="Clear all blocked skills history",
)
async def delete_blocked_history() -> dict:
    from ...security.skill_scanner import clear_blocked_history

    clear_blocked_history()
    return {"cleared": True}


@router.delete(
    "/security/skill-scanner/blocked-history/{index}",
    summary="Remove a single blocked history entry",
)
async def delete_blocked_entry(
    index: int = Path(..., ge=0),
) -> dict:
    from ...security.skill_scanner import remove_blocked_entry

    ok = remove_blocked_entry(index)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"removed": True}


class WhitelistAddRequest(BaseModel):
    skill_name: str
    content_hash: str = ""


@router.post(
    "/security/skill-scanner/whitelist",
    summary="Add a skill to the whitelist",
)
async def add_to_whitelist(
    body: WhitelistAddRequest = Body(...),
) -> dict:
    skill_name = body.skill_name.strip()
    content_hash = body.content_hash
    if not skill_name:
        raise HTTPException(status_code=400, detail="skill_name is required")

    config = load_config()
    scanner_cfg = config.security.skill_scanner

    for entry in scanner_cfg.whitelist:
        if entry.skill_name == skill_name:
            raise HTTPException(
                status_code=409,
                detail=f"Skill '{skill_name}' is already whitelisted",
            )

    scanner_cfg.whitelist.append(
        SkillScannerWhitelistEntry(
            skill_name=skill_name,
            content_hash=content_hash,
            added_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    save_config(config)
    return {"whitelisted": True, "skill_name": skill_name}


@router.delete(
    "/security/skill-scanner/whitelist/{skill_name}",
    summary="Remove a skill from the whitelist",
)
async def remove_from_whitelist(
    skill_name: str = Path(..., min_length=1),
) -> dict:
    config = load_config()
    scanner_cfg = config.security.skill_scanner
    original_len = len(scanner_cfg.whitelist)
    scanner_cfg.whitelist = [
        e for e in scanner_cfg.whitelist if e.skill_name != skill_name
    ]
    if len(scanner_cfg.whitelist) == original_len:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}' not found in whitelist",
        )
    save_config(config)
    return {"removed": True, "skill_name": skill_name}
