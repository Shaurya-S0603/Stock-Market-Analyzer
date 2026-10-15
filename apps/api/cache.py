"""Optional owner-scoped Redis cache and atomic write rate limit.

Database queries remain authoritative. Redis keys never contain raw GitHub IDs.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
import redis
from redis.exceptions import RedisError

from apps.api.auth import OwnerId

_TTL = 15
_WRITE_LIMIT = 60
_RATE_WINDOW = 60
_ATOMIC_WINDOW = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""

@lru_cache(maxsize=3)
def _client(url: str) -> redis.Redis:
    return redis.Redis.from_url(url, decode_responses=True,
                                socket_connect_timeout=0.5, socket_timeout=0.5)

def _key(subject: str, prefix: str) -> str:
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    return "qe:v3:" + prefix + ":" + digest

def cached_lists(subject: str) -> dict | None:
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        value = _client(url).get(_key(subject, "watchlists"))
        if value:
            decoded = json.loads(value)
            if isinstance(decoded, dict) and isinstance(decoded.get("watchlists"), list):
                return decoded
    except (RedisError, ValueError, TypeError):
        pass
    return None

def remember_lists(subject: str, payload: dict):
    url = os.getenv("REDIS_URL")
    if url:
        try:
            _client(url).setex(_key(subject, "watchlists"), _TTL,
                               json.dumps(payload, separators=(",", ":")))
        except RedisError:
            pass

def invalidate_lists(subject: str):
    url = os.getenv("REDIS_URL")
    if url:
        try:
            _client(url).delete(_key(subject, "watchlists"))
        except RedisError:
            pass

def throttled_subject(subject: OwnerId) -> str:
    """Atomic fixed-window cap on authenticated writes; optional for local mode."""
    url = os.getenv("REDIS_URL")
    require_redis = os.getenv("QUANTEDGE_REQUIRE_REDIS") == "1"
    if not url:
        if require_redis:
            raise HTTPException(status_code=503, detail="Required rate limiter unavailable")
        return subject
    try:
        count = int(_client(url).eval(_ATOMIC_WINDOW, 1, _key(subject, "writes"), _RATE_WINDOW))
    except (RedisError, ValueError, TypeError) as exc:
        if require_redis:
            raise HTTPException(status_code=503, detail="Required rate limiter unavailable") from exc
        return subject
    if count > _WRITE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many saved research changes",
                            headers={"Retry-After": str(_RATE_WINDOW)})
    return subject

ThrottledOwner = Annotated[str, Depends(throttled_subject)]
