# -*- coding: utf-8 -*-
"""SWE 定时任务恢复预热服务."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from ....config.constant import (
    SWE_API_BASE_URL,
    SWE_WARMUP_CONCURRENCY,
    SWE_WARMUP_CRON_TABLE,
    SWE_WARMUP_ENDPOINT,
    SWE_WARMUP_HEADERS_JSON,
    SWE_WARMUP_RETRIES,
    SWE_WARMUP_RETRY_DELAY_SECONDS,
    SWE_WARMUP_TIMEOUT_SECONDS,
)
from ...database import get_db_connection

logger = logging.getLogger(__name__)


class WarmupTarget(BaseModel):
    """需要触发 SWE 加载的租户用户."""

    tenant_id: str
    user_id: str
    source_id: str = ""
    bbk_id: str = ""


class UserWarmupResult(BaseModel):
    """单个用户预热结果."""

    user_id: str
    success: bool
    status_code: Optional[int] = None
    attempts: int = 0
    error: str = ""


class WarmupStatus(BaseModel):
    """最近一次预热任务状态."""

    running: bool = False
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    users: list[UserWarmupResult] = Field(default_factory=list)
    last_error: str = ""


def parse_fixed_headers(headers_json: str) -> dict[str, str]:
    """解析预配置 HTTP headers."""
    if not headers_json.strip():
        return {}

    try:
        parsed = json.loads(headers_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "MONITOR_SWE_WARMUP_HEADERS_JSON 不是合法 JSON"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError("MONITOR_SWE_WARMUP_HEADERS_JSON 必须是对象")

    headers: dict[str, str] = {}
    for key, value in parsed.items():
        # 环境变量中的 header 值统一转为字符串，避免 httpx 收到非字符串类型。
        if key and value is not None:
            headers[str(key)] = str(value)
    return headers


def _mask_header_value(name: str, value: str) -> str:
    """脱敏 header 值，避免调试日志泄露认证信息."""
    lower_name = name.lower()
    if lower_name in {"authorization", "cookie", "x-header-cookie"}:
        if not value:
            return ""
        if len(value) <= 12:
            return "***"
        return f"{value[:8]}...{value[-4:]}"
    return value


def format_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
    """生成可安全打印的 header 快照."""
    return {
        name: _mask_header_value(name, value)
        for name, value in sorted(headers.items())
    }


class SweCronWarmupService:
    """通过调用 SWE 接口恢复租户定时任务内存调度."""

    def __init__(
        self,
        *,
        cron_table: str = SWE_WARMUP_CRON_TABLE,
        base_url: str = SWE_API_BASE_URL,
        endpoint: str = SWE_WARMUP_ENDPOINT,
        headers_json: str = SWE_WARMUP_HEADERS_JSON,
        concurrency: int = SWE_WARMUP_CONCURRENCY,
        retries: int = SWE_WARMUP_RETRIES,
        retry_delay_seconds: float = SWE_WARMUP_RETRY_DELAY_SECONDS,
        timeout_seconds: float = SWE_WARMUP_TIMEOUT_SECONDS,
    ) -> None:
        """初始化预热服务."""
        self._cron_table = cron_table
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint
        self._fixed_headers = parse_fixed_headers(headers_json)
        self._concurrency = max(1, concurrency)
        self._retries = max(0, retries)
        self._retry_delay_seconds = max(0.0, retry_delay_seconds)
        self._timeout_seconds = max(1.0, timeout_seconds)
        self._status = WarmupStatus()
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    def get_status(self) -> WarmupStatus:
        """返回最近一次预热状态快照."""
        return self._status.model_copy(deep=True)

    def _build_url(self) -> str:
        endpoint = self._endpoint
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self._base_url}{endpoint}"

    def build_headers(self, target: WarmupTarget) -> dict[str, str]:
        """构造单个租户请求头."""
        headers = dict(self._fixed_headers)
        # 身份头必须来自定时任务表，防止固定 header 中的旧值串租户。
        headers["X-User-Id"] = target.user_id
        headers["X-Tenant-Id"] = target.tenant_id
        if target.source_id:
            headers["X-Source-Id"] = target.source_id
        if target.bbk_id:
            headers["X-Bbk-Id"] = target.bbk_id
        return headers

    async def start_background(self) -> WarmupStatus:
        """启动后台预热任务，已有任务运行时直接返回当前状态."""
        await self.schedule_background()
        return self.get_status()

    async def schedule_background(
        self,
        start_delay_seconds: float = 0.0,
    ) -> Optional[asyncio.Task[Any]]:
        """调度后台预热任务，避免自动和手动触发重复执行."""
        async with self._lock:
            # 自动启动和人工补跑可能同时触发，同一时刻只允许一轮预热。
            if self._task and not self._task.done():
                return self._task
            self._status = WarmupStatus(
                running=True,
                started_at=datetime.now(timezone.utc),
            )
            self._task = asyncio.create_task(
                self._run_with_delay(start_delay_seconds),
            )
            return self._task

    async def _run_with_delay(
        self, start_delay_seconds: float
    ) -> WarmupStatus:
        try:
            if start_delay_seconds > 0:
                # 给 SWE 主服务和网关留出初始化时间，降低容器冷启动竞态。
                await asyncio.sleep(start_delay_seconds)
            return await self.warmup_all()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # 预热是恢复能力，失败不应该拖垮 Monitor 主服务。
            logger.exception("SWE cron warmup crashed")
            self._status = WarmupStatus(
                running=False,
                started_at=self._status.started_at,
                finished_at=datetime.now(timezone.utc),
                last_error=repr(exc),
            )
            return self.get_status()

    @staticmethod
    def _normalize_table_name(table_name: str) -> str:
        """校验表名，避免环境变量被拼成危险 SQL."""
        parts = [part.strip("`") for part in table_name.split(".")]
        if not parts or len(parts) > 2:
            raise ValueError("MONITOR_SWE_WARMUP_CRON_TABLE 表名不合法")
        for part in parts:
            if not part or not part.replace("_", "").isalnum():
                raise ValueError("MONITOR_SWE_WARMUP_CRON_TABLE 表名不合法")
        return ".".join(f"`{part}`" for part in parts)

    async def discover_targets(self) -> list[WarmupTarget]:
        """从定时任务表发现需要恢复的租户用户."""
        db = get_db_connection()
        table_name = self._normalize_table_name(self._cron_table)
        rows = await db.fetch_all(
            f"""
            SELECT tenant_id, creator_user_id, source_id, bbk_id
            FROM {table_name}
            WHERE enabled = 1 AND deleted_at IS NULL
            ORDER BY updated_at DESC, created_at DESC
            """,
        )

        targets: dict[tuple[str, str], WarmupTarget] = {}
        for row in rows:
            tenant_id = str(row.get("tenant_id") or "").strip()
            if not tenant_id:
                continue

            user_id = str(row.get("creator_user_id") or "").strip()
            if not user_id:
                user_id = tenant_id

            # 一个用户可能创建多个定时任务，只需触发一次 SWE runtime 加载。
            key = (tenant_id, user_id)
            if key in targets:
                continue

            targets[key] = WarmupTarget(
                tenant_id=tenant_id,
                user_id=user_id,
                source_id=str(row.get("source_id") or "").strip(),
                bbk_id=str(row.get("bbk_id") or "").strip(),
            )

        return list(targets.values())

    async def warmup_all(self) -> WarmupStatus:
        """查询启用定时任务的用户并触发 SWE 恢复调度."""
        started_at = datetime.now(timezone.utc)
        targets = await self.discover_targets()
        self._status = WarmupStatus(
            running=True,
            started_at=started_at,
            total=len(targets),
        )

        if not targets:
            self._status.running = False
            self._status.finished_at = datetime.now(timezone.utc)
            logger.info("No active cron users found for SWE warmup")
            return self.get_status()

        logger.info("Starting SWE cron warmup for %d users", len(targets))
        # 限制并发，避免多租户同时打到刚启动的 SWE runtime。
        semaphore = asyncio.Semaphore(self._concurrency)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            tasks = [
                self._warmup_user_with_limit(client, semaphore, target)
                for target in targets
            ]
            results = await asyncio.gather(*tasks)

        succeeded = sum(1 for item in results if item.success)
        failed = len(results) - succeeded
        self._status = WarmupStatus(
            running=False,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            users=results,
        )
        logger.info(
            "SWE cron warmup finished: total=%d succeeded=%d failed=%d",
            len(results),
            succeeded,
            failed,
        )
        return self.get_status()

    async def _warmup_user_with_limit(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        target: WarmupTarget,
    ) -> UserWarmupResult:
        async with semaphore:
            return await self._warmup_user(client, target)

    async def _warmup_user(
        self,
        client: httpx.AsyncClient,
        target: WarmupTarget,
    ) -> UserWarmupResult:
        url = self._build_url()
        headers = self.build_headers(target)
        last_error = ""
        last_status_code: Optional[int] = None

        for attempt in range(1, self._retries + 2):
            try:
                # 响应体内容不重要；2xx 表示 SWE 已经经过租户/agent 加载链路。
                logger.info(
                    "SWE cron warmup request: tenant_id=%s user_id=%s "
                    "attempt=%s url=%s headers=%s",
                    target.tenant_id,
                    target.user_id,
                    attempt,
                    url,
                    format_headers_for_log(headers),
                )
                response = await client.get(url, headers=headers)
                last_status_code = response.status_code
                if 200 <= response.status_code < 300:
                    return UserWarmupResult(
                        user_id=target.user_id,
                        success=True,
                        status_code=response.status_code,
                        attempts=attempt,
                    )
                last_error = response.text[:500]
            except Exception as exc:  # pylint: disable=broad-except
                last_error = repr(exc)

            if attempt <= self._retries and self._retry_delay_seconds > 0:
                # 覆盖 SWE 或网关短时间未就绪的情况，失败细节留到最后一次记录。
                await asyncio.sleep(self._retry_delay_seconds)

        logger.warning(
            "SWE cron warmup failed: tenant_id=%s user_id=%s status=%s error=%s",
            target.tenant_id,
            target.user_id,
            last_status_code,
            last_error,
        )
        return UserWarmupResult(
            user_id=target.user_id,
            success=False,
            status_code=last_status_code,
            attempts=self._retries + 1,
            error=last_error,
        )


_warmup_service: Optional[SweCronWarmupService] = None


def get_swe_cron_warmup_service() -> SweCronWarmupService:
    """返回全局 SWE cron 预热服务."""
    global _warmup_service
    if _warmup_service is None:
        _warmup_service = SweCronWarmupService()
    return _warmup_service
