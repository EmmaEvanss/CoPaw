# -*- coding: utf-8 -*-
"""Source 系统配置运行时服务与缓存。"""

import logging
import time
from dataclasses import dataclass
from typing import Callable

from .models import (
    CurrentSourceSystemConfigResponse,
    DEFAULT_SOURCE_SYSTEM_CONFIG,
    EffectiveSourceSystemConfig,
    SourceSystemConfig,
    SourceSystemConfigRecord,
    SourceSystemConfigUpsert,
)
from .registry import prune_registered_default_overrides
from .store import SourceSystemConfigStore, SourceSystemConfigStoreUnavailable

logger = logging.getLogger(__name__)


class SourceSystemConfigUnavailable(RuntimeError):
    """Source 系统配置存储不可用且没有可用缓存。"""


class SourceSystemConfigDataInvalid(RuntimeError):
    """Source 系统配置数据损坏且没有可用缓存。"""


@dataclass
class _CacheEntry:
    """缓存项包含配置、完整加载时间和最近探测时间。"""

    effective: EffectiveSourceSystemConfig
    loaded_at: float
    checked_at: float


class SourceSystemConfigService:
    """解析 source effective config，并提供版本探测缓存。"""

    def __init__(
        self,
        store: SourceSystemConfigStore,
        ttl_seconds: int = 30,
        probe_interval_seconds: int | None = None,
        time_fn: Callable[[], float] | None = None,
    ):
        """初始化运行时服务。"""
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.probe_interval_seconds = max(
            1,
            (
                probe_interval_seconds
                if probe_interval_seconds is not None
                else 10
            ),
        )
        self._time_fn = time_fn or time.time
        self._cache: dict[str, _CacheEntry] = {}

    async def resolve_config(
        self,
        source_id: str,
        *,
        force_refresh: bool = False,
    ) -> EffectiveSourceSystemConfig:
        """解析 source 的 effective config。"""
        now = self._time_fn()
        cached = self._cache.get(source_id)
        cache_ttl_valid = (
            cached is not None
            and not force_refresh
            and self._is_cache_within_ttl(cached, now)
        )
        if cache_ttl_valid:
            assert cached is not None
            if self._is_probe_window_open(cached, now):
                return cached.effective

        try:
            if cache_ttl_valid:
                assert cached is not None
                remote_version = await self.store.get_config_version(source_id)
                cached_version = int(cached.effective.version)
                current_version = int(remote_version or 0)
                if current_version == cached_version:
                    fresh = cached.effective.model_copy(
                        update={"stale": False, "last_error": None},
                    )
                    self._cache[source_id] = _CacheEntry(
                        fresh,
                        cached.loaded_at,
                        now,
                    )
                    return fresh

            record = await self.store.get_config(source_id)
            effective = self._build_effective(source_id, record)
            self._cache[source_id] = _CacheEntry(effective, now, now)
            return effective
        except SourceSystemConfigStoreUnavailable as exc:
            return self._fallback_on_error(source_id, cached, now, exc)
        except ValueError as exc:
            if cached is not None:
                return self._fallback_on_error(source_id, cached, now, exc)
            raise SourceSystemConfigDataInvalid(
                (
                    "source system config data is invalid "
                    f"for {source_id}: {exc}"
                ),
            ) from exc
        except Exception as exc:
            if cached is not None:
                return self._fallback_on_error(source_id, cached, now, exc)
            raise SourceSystemConfigUnavailable(
                f"source system config unavailable for {source_id}: {exc}",
            ) from exc

    async def resolve_raw_config(
        self,
        source_id: str,
    ) -> CurrentSourceSystemConfigResponse:
        """读取当前 source 的原始配置，不合成默认值。"""
        try:
            record = await self.store.get_config(source_id)
        except SourceSystemConfigStoreUnavailable:
            raise
        except ValueError:
            raise
        except Exception as exc:
            raise SourceSystemConfigUnavailable(
                f"source system config unavailable for {source_id}: {exc}",
            ) from exc

        return self._build_raw_response(source_id, record)

    async def upsert_current_source_config(
        self,
        source_id: str,
        config: SourceSystemConfig,
        *,
        updated_by: str | None,
    ) -> CurrentSourceSystemConfigResponse:
        """保存 current-source 原始配置，并按注册默认值裁剪。"""
        pruned_config = SourceSystemConfig.model_validate(
            prune_registered_default_overrides(config.as_dict()),
        )
        if not pruned_config.as_dict():
            await self.store.delete_config(source_id)
            self.invalidate(source_id)
            return self._build_raw_response(source_id, None)

        record = await self.store.upsert_config(
            source_id,
            SourceSystemConfigUpsert(
                config=pruned_config,
                updated_by=updated_by,
            ),
        )
        self.invalidate(source_id)
        return self._build_raw_response(source_id, record)

    async def delete_current_source_config(self, source_id: str) -> bool:
        """删除 current-source 原始配置。"""
        deleted = await self.store.delete_config(source_id)
        self.invalidate(source_id)
        return deleted

    def _is_cache_within_ttl(
        self,
        cached: _CacheEntry,
        now: float,
    ) -> bool:
        """判断缓存是否仍在调用方声明的 TTL 内。"""
        return now - cached.loaded_at < self.ttl_seconds

    def _is_probe_window_open(
        self,
        cached: _CacheEntry,
        now: float,
    ) -> bool:
        """判断最近一次探测是否仍在免探测窗口内。"""
        return now - cached.checked_at < self.probe_interval_seconds

    def invalidate(self, source_id: str | None = None) -> None:
        """清理缓存，管理接口更新后当前实例立即生效。"""
        if source_id is None:
            self._cache.clear()
            return
        self._cache.pop(source_id, None)

    def _fallback_on_error(
        self,
        source_id: str,
        cached: _CacheEntry | None,
        now: float,
        exc: Exception,
    ) -> EffectiveSourceSystemConfig:
        """存储异常时返回 stale 缓存或 stale 默认配置。"""
        if cached is not None:
            logger.warning(
                "使用 source 配置缓存兜底: source=%s, error=%s",
                source_id,
                exc,
            )
            stale = cached.effective.model_copy(
                update={
                    "stale": True,
                    "last_error": str(exc),
                },
            )
            self._cache[source_id] = _CacheEntry(
                stale,
                cached.loaded_at,
                now,
            )
            return stale
        fallback = self._build_effective(source_id, None).model_copy(
            update={
                "stale": True,
                "last_error": str(exc),
            },
        )
        self._cache[source_id] = _CacheEntry(fallback, now, now)
        return fallback

    def _build_effective(
        self,
        source_id: str,
        record: SourceSystemConfigRecord | None,
    ) -> EffectiveSourceSystemConfig:
        """将默认配置和 source 覆盖合成为运行时配置。"""
        if record is None:
            return EffectiveSourceSystemConfig(
                source_id=source_id,
                config=DEFAULT_SOURCE_SYSTEM_CONFIG,
                version=0,
                is_default=True,
            )

        return EffectiveSourceSystemConfig(
            source_id=source_id,
            config=record.config.merged_with_defaults(),
            version=record.version,
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )

    def _build_raw_response(
        self,
        source_id: str,
        record: SourceSystemConfigRecord | None,
    ) -> CurrentSourceSystemConfigResponse:
        """构造 current-source 原始配置响应。"""
        if record is None:
            return CurrentSourceSystemConfigResponse(
                source_id=source_id,
                config=SourceSystemConfig.model_validate({}),
                version=0,
                is_default=True,
                updated_by=None,
                updated_at=None,
            )

        return CurrentSourceSystemConfigResponse(
            source_id=record.source_id,
            config=record.config,
            version=record.version,
            is_default=False,
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )
