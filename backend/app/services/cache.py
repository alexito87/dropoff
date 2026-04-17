
from __future__ import annotations

import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis cache facade with graceful fallback.

    Redis is optional:
    - if unavailable, methods return safe defaults
    - DB remains the source of truth
    """

    def __init__(self) -> None:
        self._client: Redis | None = None
        self._disabled = not settings.REDIS_ENABLED

    def _get_client(self) -> Redis | None:
        if self._disabled:
            return None

        if self._client is not None:
            return self._client

        try:
            self._client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            )
            return self._client
        except Exception:
            logger.exception("Failed to create Redis client")
            return None

    def ping(self) -> bool:
        client = self._get_client()
        if client is None:
            return False

        try:
            return bool(client.ping())
        except RedisError:
            logger.exception("Redis ping failed")
            return False

    def get(self, key: str) -> str | None:
        client = self._get_client()
        if client is None:
            return None

        try:
            return client.get(key)
        except RedisError:
            logger.exception("Redis GET failed for key=%s", key)
            return None

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> bool:
        client = self._get_client()
        if client is None:
            return False

        try:
            if ttl_seconds is not None:
                client.set(name=key, value=value, ex=ttl_seconds)
            else:
                client.set(name=key, value=value)
            return True
        except RedisError:
            logger.exception("Redis SET failed for key=%s", key)
            return False

    def delete(self, *keys: str) -> int:
        client = self._get_client()
        if client is None or not keys:
            return 0

        try:
            return int(client.delete(*keys))
        except RedisError:
            logger.exception("Redis DELETE failed for keys=%s", keys)
            return 0

    def incr(self, key: str) -> int | None:
        client = self._get_client()
        if client is None:
            return None

        try:
            return int(client.incr(key))
        except RedisError:
            logger.exception("Redis INCR failed for key=%s", key)
            return None

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        if raw is None:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.exception("Failed to decode cached JSON for key=%s", key)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        try:
            payload = json.dumps(value, default=str)
        except TypeError:
            logger.exception("Failed to serialize cached JSON for key=%s", key)
            return False

        return self.set(key=key, value=payload, ttl_seconds=ttl_seconds)

    def get_namespace_version(self, namespace: str) -> int:
        """
        Returns a numeric namespace version.
        If Redis is unavailable, safely falls back to version 1.
        """
        key = f"cache_namespace:{namespace}:version"
        raw_value = self.get(key)

        if raw_value is None:
            created = self.set(key=key, value="1")
            if created:
                return 1

            # fallback when Redis is unavailable
            return 1

        try:
            return int(raw_value)
        except ValueError:
            logger.warning("Invalid namespace version for key=%s; resetting to 1", key)
            self.set(key=key, value="1")
            return 1

    def bump_namespace_version(self, namespace: str) -> int:
        """
        Used for catalog/search namespace invalidation.
        If Redis is unavailable, safely falls back to version 1.
        """
        key = f"cache_namespace:{namespace}:version"
        value = self.incr(key)
        if value is not None:
            return value

        return 1


cache_service = CacheService()

