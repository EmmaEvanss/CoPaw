# -*- coding: utf-8 -*-
"""Elasticsearch client for Monitor service."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global client singleton
_es_client: Optional["ESClient"] = None


class ESClient:
    """Async Elasticsearch client for model output queries."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str = "",
        password: str = "",
        index: str = "swe_messages",
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

        if self._user and self._password:
            kwargs["basic_auth"] = (self._user, self._password)

        try:
            self._es = AsyncElasticsearch(**kwargs)
            await self._es.ping()
            self._connected = True
            logger.info(
                "Elasticsearch connected: %s:%s",
                self._host,
                self._port,
            )
        except Exception as e:
            logger.warning("Failed to connect to Elasticsearch: %s", e)
            self._connected = False

    async def get_message(self, trace_id: str) -> Optional[str]:
        """Get model output by trace ID."""
        if not self._connected or not self._es:
            return None

        try:
            result = await self._es.get(index=self._index, id=trace_id)
            if result and result.get("found"):
                return result["_source"].get("model_output")
        except Exception:
            pass
        return None

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
        ES_PASSWORD,
        ES_INDEX,
    )

    if not ES_HOST:
        _es_client = None
        return None

    _es_client = ESClient(ES_HOST, ES_PORT, ES_USER, ES_PASSWORD, ES_INDEX)
    await _es_client.connect()
    return _es_client


async def close_es_client() -> None:
    """Close the global ES client."""
    global _es_client

    if _es_client is not None:
        await _es_client.close()
        _es_client = None
