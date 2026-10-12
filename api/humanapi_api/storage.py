"""Where proof photos live. The database keeps the record (who, which task, when, where); the bytes go here.

Redis in production (`HA_REDIS_URL`), memory otherwise. Photos expire after `ttl_days`, which matches the purge of
task content. The interface is small on purpose, so the bytes can move to file storage later without other changes.
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

logger = logging.getLogger("humanapi.api.storage")

PHOTO_TTL_DAYS = 90


class PhotoStore(Protocol):
    def put(self, photo_id: str, data: bytes, content_type: str) -> None: ...
    def get(self, photo_id: str) -> tuple[bytes, str] | None: ...
    def delete(self, photo_id: str) -> None: ...
    def ok(self) -> bool: ...


class MemoryPhotos:
    def __init__(self) -> None:
        self._d: dict[str, tuple[bytes, str, float]] = {}

    def put(self, photo_id: str, data: bytes, content_type: str) -> None:
        self._d[photo_id] = (data, content_type, time.time())

    def get(self, photo_id: str) -> tuple[bytes, str] | None:
        hit = self._d.get(photo_id)
        return (hit[0], hit[1]) if hit else None

    def delete(self, photo_id: str) -> None:
        self._d.pop(photo_id, None)

    def ok(self) -> bool:
        return True


class RedisPhotos:
    def __init__(self, url: str, ttl_days: int = PHOTO_TTL_DAYS):
        import redis

        self.r = redis.from_url(url, socket_timeout=15, socket_connect_timeout=10, retry_on_timeout=True)
        self.ttl = ttl_days * 86400

    def put(self, photo_id: str, data: bytes, content_type: str) -> None:
        with self.r.pipeline() as p:
            p.set(f"photo:{photo_id}", data, ex=self.ttl)
            p.set(f"photo:{photo_id}:type", content_type, ex=self.ttl)
            p.execute()

    def get(self, photo_id: str) -> tuple[bytes, str] | None:
        data, ct = self.r.mget(f"photo:{photo_id}", f"photo:{photo_id}:type")
        if data is None:
            return None
        return bytes(data), (ct.decode() if isinstance(ct, bytes) else ct) or "image/jpeg"

    def delete(self, photo_id: str) -> None:
        self.r.delete(f"photo:{photo_id}", f"photo:{photo_id}:type")

    def ok(self) -> bool:
        try:
            return bool(self.r.ping())
        except Exception:
            return False


def build(url: str) -> PhotoStore:
    if url:
        return RedisPhotos(url)
    logger.warning("no HA_REDIS_URL: proof photos are kept in memory and are lost on restart")
    return MemoryPhotos()


def sniff(data: bytes) -> str | None:
    """The real image type from the bytes, or None when it is not a photo format we accept."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypheif"):
        return "image/heic"
    return None
