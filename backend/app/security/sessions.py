"""Redis-backed server-side sessions.

The cookie carries only a random opaque session id; the user id, league
selection, and CSRF token live inside Redis.  Sessions slide: each touch
resets the TTL.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from typing import Any

from redis.asyncio import Redis

_SESSION_KEY_PREFIX = "sess:"
_PENDING_AUTH_PREFIX = "oauth:pending:"
_REFRESH_COOLDOWN_PREFIX = "refresh:cooldown:"


def _session_key(sid: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{sid}"


def _pending_key(state: str) -> str:
    return f"{_PENDING_AUTH_PREFIX}{state}"


@dataclass
class SessionData:
    user_id: str
    csrf: str
    league: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, blob: str) -> SessionData:
        raw = json.loads(blob)
        return cls(**raw)


class SessionStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def create(self, user_id: str, *, league: str | None = None) -> tuple[str, SessionData]:
        sid = secrets.token_urlsafe(32)
        data = SessionData(user_id=user_id, csrf=secrets.token_urlsafe(32), league=league)
        await self._redis.set(_session_key(sid), data.to_json(), ex=self._ttl)
        return sid, data

    async def get(self, sid: str) -> SessionData | None:
        blob = await self._redis.get(_session_key(sid))
        if blob is None:
            return None
        # Sliding window refresh.
        await self._redis.expire(_session_key(sid), self._ttl)
        return SessionData.from_json(blob if isinstance(blob, str) else blob.decode("utf-8"))

    async def update(self, sid: str, data: SessionData) -> None:
        await self._redis.set(_session_key(sid), data.to_json(), ex=self._ttl)

    async def destroy(self, sid: str) -> None:
        await self._redis.delete(_session_key(sid))


@dataclass
class PendingAuth:
    verifier: str
    redirect_after: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, blob: str) -> PendingAuth:
        return cls(**json.loads(blob))


class PendingAuthStore:
    """Stores the in-flight OAuth2 code-verifier keyed by ``state``.

    The entry is *consumed* on the callback: a successful ``GETDEL`` guarantees
    the state cannot be replayed.  TTL is a few minutes.
    """

    TTL_SECONDS = 5 * 60

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def put(self, state: str, pending: PendingAuth) -> None:
        await self._redis.set(_pending_key(state), pending.to_json(), ex=self.TTL_SECONDS)

    async def consume(self, state: str) -> PendingAuth | None:
        blob: Any = await self._redis.getdel(_pending_key(state))
        if blob is None:
            return None
        if isinstance(blob, bytes):
            blob = blob.decode("utf-8")
        return PendingAuth.from_json(blob)


class RefreshCooldown:
    """Per-user rate-limit on manual /api/refresh calls."""

    def __init__(self, redis: Redis, cooldown_seconds: int) -> None:
        self._redis = redis
        self._cd = cooldown_seconds

    async def try_acquire(self, user_id: str) -> bool:
        key = f"{_REFRESH_COOLDOWN_PREFIX}{user_id}"
        acquired = await self._redis.set(key, "1", nx=True, ex=self._cd)
        return bool(acquired)

    async def remaining(self, user_id: str) -> int:
        key = f"{_REFRESH_COOLDOWN_PREFIX}{user_id}"
        ttl = await self._redis.ttl(key)
        return max(int(ttl), 0)
