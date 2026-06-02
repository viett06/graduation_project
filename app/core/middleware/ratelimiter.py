import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis import redis_config
from app.core.security.rbac import RoleEnum


SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local window_time = tonumber(ARGV[4])
local unique_id = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local count = redis.call('ZCARD', key)

if count >= max_requests then
    return 1
end

redis.call('ZADD', key, now, unique_id)
redis.call('EXPIRE', key, window_time + 1)
return 0
"""


TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])

local time_parts = redis.call('TIME')
local now = tonumber(time_parts[1]) + tonumber(time_parts[2]) / 1e6

local bucket   = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens   = tonumber(bucket[1]) or capacity
local last     = tonumber(bucket[2]) or now

local elapsed  = now - last
local refilled = math.min(capacity, tokens + elapsed * rate)
local ttl      = math.ceil(capacity / rate) + 60

if refilled >= 1 then
    redis.call('HMSET', key, 'tokens', refilled - 1, 'last_refill', now)
    redis.call('EXPIRE', key, ttl)
    return 0
else
    redis.call('HMSET', key, 'tokens', refilled, 'last_refill', now)
    redis.call('EXPIRE', key, ttl)
    return 1
end
"""


@dataclass(frozen=True)
class RateLimitPolicy:
    capacity: float
    refill_rate: float
    max_requests: int
    window_time: int


RATE_LIMIT_POLICIES: dict[str, RateLimitPolicy] = {
    "guest": RateLimitPolicy(capacity=5, refill_rate=0.2, max_requests=20, window_time=60),
    "user": RateLimitPolicy(capacity=30, refill_rate=1.0, max_requests=120, window_time=60),
    "admin": RateLimitPolicy(capacity=100, refill_rate=5.0, max_requests=600, window_time=60),
}

PUBLIC_PATH_PREFIXES = (
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else "unknown"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


def _decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "access":
        return None

    return payload


def _role_scope(payload: dict[str, Any] | None) -> str:
    roles = payload.get("roles", []) if payload else []

    if RoleEnum.ADMIN.value in roles:
        return "admin"

    return "user"


def _rate_limit_identity(request: Request) -> tuple[str, str]:
    token = _extract_bearer_token(request)
    if not token:
        return "guest", f"ip:{_client_ip(request)}"

    payload = _decode_access_token(token)
    if not payload:
        return "guest", f"ip:{_client_ip(request)}"

    user_id = payload.get("user_id") or payload.get("sub")
    role_scope = _role_scope(payload)

    if user_id is None:
        return role_scope, f"token:{_hash_token(token)}"

    return role_scope, f"user:{user_id}"


def _build_key(role_scope: str, identity: str) -> str:
    return f"rate_limit:{role_scope}:{identity}"


def _is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_PATH_PREFIXES)


async def _consume_sliding_window(redis, key: str, max_requests: int, window_time: int) -> bool:
    now = time.time()
    result = await redis.eval(
        SLIDING_WINDOW_LUA,
        1,
        f"window:{key}",
        now,
        now - window_time,
        max_requests,
        window_time,
        str(uuid.uuid4()),
    )
    return bool(result)


async def _consume_token_bucket(redis, key: str, capacity: float, refill_rate: float) -> bool:
    result = await redis.eval(
        TOKEN_BUCKET_LUA,
        1,
        f"bucket:{key}",
        capacity,
        refill_rate,
    )
    return bool(result)


async def _is_rate_limited(request: Request) -> bool:
    redis = redis_config.redis_client
    if redis is None:
        return False

    role_scope, identity = _rate_limit_identity(request)
    policy = RATE_LIMIT_POLICIES.get(role_scope, RATE_LIMIT_POLICIES["guest"])
    key = _build_key(role_scope, identity)

    window_limited = await _consume_sliding_window(
        redis,
        key,
        policy.max_requests,
        policy.window_time,
    )
    if window_limited:
        return True

    return await _consume_token_bucket(
        redis,
        key,
        policy.capacity,
        policy.refill_rate,
    )


async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or _is_public_path(request.url.path):
        return await call_next(request)

    try:
        limited = await _is_rate_limited(request)
    except Exception as exc:
        print(f"Rate limit error: {exc}")
        limited = False

    if limited:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": "1"},
        )

    return await call_next(request)
