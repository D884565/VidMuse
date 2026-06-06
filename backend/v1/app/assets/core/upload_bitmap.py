from __future__ import annotations

from threading import Lock
from typing import Optional

from redis import Redis
from redis.exceptions import RedisError

from backend.v1.app.config.config import settings


class _MemoryBitmapClient:
    def __init__(self) -> None:
        self._bitmaps: dict[str, bytearray] = {}
        self._lock = Lock()

    def setbit(self, key: str, offset: int, value: int) -> int:
        with self._lock:
            bitmap = self._ensure_bitmap(key, offset)
            byte_index = offset // 8
            bit_offset = 7 - (offset % 8)
            old_value = 1 if bitmap[byte_index] & (1 << bit_offset) else 0
            if value:
                bitmap[byte_index] |= 1 << bit_offset
            else:
                bitmap[byte_index] &= ~(1 << bit_offset)
            return old_value

    def getbit(self, key: str, offset: int) -> int:
        with self._lock:
            bitmap = self._bitmaps.get(key)
            if bitmap is None:
                return 0
            byte_index = offset // 8
            if byte_index >= len(bitmap):
                return 0
            bit_offset = 7 - (offset % 8)
            return 1 if bitmap[byte_index] & (1 << bit_offset) else 0

    def delete(self, key: str) -> int:
        with self._lock:
            existed = key in self._bitmaps
            self._bitmaps.pop(key, None)
            return 1 if existed else 0

    def _ensure_bitmap(self, key: str, offset: int) -> bytearray:
        bitmap = self._bitmaps.setdefault(key, bytearray())
        byte_index = offset // 8
        if byte_index >= len(bitmap):
            bitmap.extend(b"\x00" * (byte_index - len(bitmap) + 1))
        return bitmap


_memory_bitmap_client = _MemoryBitmapClient()
_redis_client: Optional[Redis] = None
_redis_client_lock = Lock()


def _build_redis_client() -> Redis:
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=2,
        decode_responses=False,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def _get_bitmap_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    with _redis_client_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            client = _build_redis_client()
            client.ping()
            _redis_client = client
        except RedisError:
            _redis_client = _memory_bitmap_client
        return _redis_client


class UploadBitmapStore:
    def set_bit(self, key: str, index: int) -> None:
        client = _get_bitmap_client()
        client.setbit(key, index, 1)

    def get_uploaded_indexes(self, key: str, total_chunks: int) -> list[int]:
        client = _get_bitmap_client()
        return [index for index in range(total_chunks) if client.getbit(key, index) == 1]

    def is_complete(self, key: str, total_chunks: int) -> bool:
        return len(self.get_uploaded_indexes(key, total_chunks)) == total_chunks

    def clear(self, key: str) -> None:
        client = _get_bitmap_client()
        client.delete(key)
