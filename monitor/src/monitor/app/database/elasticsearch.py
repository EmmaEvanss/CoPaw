# -*- coding: utf-8 -*-
"""Elasticsearch client for Monitor service."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ES 服务端 6.x 必须使用 doc_type，客户端 7.x 兼容传该参数
_DOC_TYPE = "_doc"

# Global client singleton
_es_client: Optional["ESClient"] = None


class ESClient:
    """Async Elasticsearch client for model output queries.

    ES 7.x 客户端兼容 ES 6.x 服务端（通过 doc_type 参数）。
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str = "",
        password: str = "",
        index: str = "swe_model_outputs",
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._index = index
        self._es = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to Elasticsearch."""
        if not self._host:
            logger.info(
                "Elasticsearch host not configured, skipping connection",
            )
            return

        try:
            from elasticsearch import AsyncElasticsearch
        except ImportError:
            logger.warning("elasticsearch package not installed")
            return

        scheme = "https" if self._port == 443 else "http"
        hosts = [f"{scheme}://{self._host}:{self._port}"]
        kwargs: dict = {"hosts": hosts}

        # ES 7.x 使用 http_auth，ES 8.x 使用 basic_auth
        if self._user and self._password:
            kwargs["http_auth"] = (self._user, self._password)

        try:
            self._es = AsyncElasticsearch(**kwargs)
            # ping() 在 401 时只警告不抛异常，需检查返回值
            if not await self._es.ping():
                logger.warning(
                    "Elasticsearch ping failed: %s:%s",
                    self._host,
                    self._port,
                )
                self._connected = False
                return

            self._connected = True
            logger.info(
                "Elasticsearch connected: %s:%s, index=%s",
                self._host,
                self._port,
                self._index,
            )
        except Exception as e:
            logger.warning("Failed to connect to Elasticsearch: %s", e)
            self._connected = False

    async def get_message(self, trace_id: str) -> Optional[str]:
        """Get model output by trace ID.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            The model_output text, or None if not found.
        """
        if not self._connected or not self._es:
            return None

        try:
            # ES 7.x 客户端传 doc_type 兼容 ES 6.x 服务端
            result = await self._es.get(
                index=self._index,
                doc_type=_DOC_TYPE,
                id=trace_id,
            )
            if result and result.get("found"):
                return result["_source"].get("model_output")
        except Exception:
            pass
        return None

    async def index_message(self, trace_id: str, model_output: str) -> bool:
        """写入 model_output 到 ES.

        Args:
            trace_id: 追踪 ID
            model_output: 模型输出文本

        Returns:
            是否写入成功
        """
        if not self._connected or not self._es:
            logger.warning("ES index skipped: connected=%s", self._connected)
            return False

        from datetime import datetime

        # ES date 类型需要毫秒精度，截断微秒部分
        now = datetime.utcnow()
        created_at = (
            now.strftime("%Y-%m-%dT%H:%M:%S")
            + f".{now.microsecond // 1000:03d}Z"
        )

        doc = {
            "trace_id": trace_id,
            "model_output": model_output,
            "created_at": created_at,
        }
        try:
            # ES 7.x 客户端传 doc_type 和 body 兼容 ES 6.x 服务端
            result = await self._es.index(
                index=self._index,
                doc_type=_DOC_TYPE,
                id=trace_id,
                body=doc,
                refresh=True,
            )
            logger.info(
                "ES index success: trace_id=%s, result=%s",
                trace_id,
                result.get("result") if result else "unknown",
            )
            return True
        except Exception as e:
            logger.warning(
                "Failed to index model_output for trace_id=%s: %s",
                trace_id,
                e,
            )
            return False

    async def close(self) -> None:
        """Close the Elasticsearch connection."""
        if self._es:
            try:
                await self._es.close()
            except Exception as e:
                logger.warning("Failed to close ES connection: %s", e)
            finally:
                self._connected = False
                self._es = None


def get_es_client() -> Optional[ESClient]:
    """Get the global ES client instance."""
    return _es_client


async def init_es_client() -> Optional[ESClient]:
    """Initialize the global ES client."""
    global _es_client

    from ...config.constant import (
        ES_HOST,
        ES_PORT,
        ES_USER,
        ES_ACCESS,
        ES_INDEX,
    )

    if not ES_HOST:
        _es_client = None
        return None

    _es_client = ESClient(ES_HOST, ES_PORT, ES_USER, ES_ACCESS, ES_INDEX)
    await _es_client.connect()
    return _es_client


async def close_es_client() -> None:
    """Close the global ES client."""
    global _es_client

    if _es_client is not None:
        await _es_client.close()
        _es_client = None
