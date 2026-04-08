import time
import json


from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool

from sqlalchemy import select
from sqlalchemy.orm import Session


from app.db.session import SessionLocal
from app.models.rate_limit import RateLimit

app = FastAPI()

def _get_db_config(path: str,method: str, session: Session):
    #hreadpool
    result = session.execute(
        select(RateLimit).filter_by(path=path, method = method).limit(1)
    )
    return result.scalar_one_or_none()

async def _get_rate_limit_config(redis, path: str,method: str, session: Session) -> dict | None:
    cache_key = f"rate_limit_config:{path}"

    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
        # return RateLimit(**data)

    config = await run_in_threadpool(_get_db_config, path,method, session)


    if config:

        data = {
            "rate_limit_capacity": float(config.rate_limit_capacity),
            "refill_rate": float(config.refill_rate),
            "max_limit_second": config.max_limit_second,
            "window_time": config.window_time,
            "max_limit_minutes": config.max_limit_minutes,
        }
        await redis.set(cache_key, json.dumps(data), ex=60)
        return data
    return None

async def _build_key(request: Request, config: dict |None) -> str:

    client_ip = request.client.host
    method = request.method
    if config is not None:
        return f"{method}:{request.url.path}:{client_ip}"
    return client_ip

async def _consume_token_capacity(redis, key: str, capacity: float, refill_rate: float, max_limit: int)-> bool:
    now = time.time()

    pipe = redis.pipeline()
    pipe.get(f"cap_token:{key}")
    pipe.get(f"cap_last_updated:{key}")
    raw_tokens, row_last_updated = await pipe.execute()

    if raw_tokens is not None:
        existing_tokens = float(raw_tokens)

    else:
        existing_tokens = capacity

    if row_last_updated is not None:
        row_last_updated = float(row_last_updated)
    else:
        row_last_updated = now

    elapsed = now - float(row_last_updated)

    refilled_tokens = existing_tokens + (elapsed * refill_rate)

    current_tokens = min(capacity, refilled_tokens)

    if current_tokens >= 1:
        current_tokens -=1
        pipe = redis.pipeline()
        pipe.set(f"cap_token:{key}", current_tokens)
        pipe.set(f"cap_last_updated:{key}", now)
        await pipe.execute()

        return False

    return True

async def _consume_token_max_limit(redis, key: str, capacity: float, refill_rate: float, max_limit: int)-> bool:
    now = time.time()

    pipe = redis.pipeline()
    pipe.get(f"max_token:{key}")
    pipe.get(f"max_last_updated:{key}")
    raw_tokens, row_last_updated = await pipe.execute()

    if raw_tokens is not None:
        existing_tokens = float(raw_tokens)

    else:
        existing_tokens = float(max_limit)

    if row_last_updated is not None:
       row_last_updated = float(row_last_updated)
    else:
        row_last_updated = now

    elapsed = now - float(row_last_updated)

    refilled_tokens = existing_tokens + (elapsed * refill_rate)

    current_tokens = min(float(max_limit), refilled_tokens)

    if current_tokens >= 1:
        current_tokens -=1
        pipe = redis.pipeline()
        pipe.set(f"max_token:{key}", current_tokens)
        pipe.set(f"max_last_updated:{key}", now)
        await pipe.execute()

        return False

    return True


async def _consume_sliding_window(redis, key: str, max_requests: int, window_time: int) -> bool:
    window_key = f"window:{key}"
    now = time.time()
    window_start = now - window_time

    pipe = redis.pipeline()
    pipe.zremrangebyscore(window_key, 0, window_start)
    pipe.zcard(window_key)
    results = await pipe.execute()

    current_count = results[1] #result zcard

    if current_count >= max_requests:
        return True

    pipe = redis.pipeline()
    pipe.zadd(window_key, {str(now): now})
    pipe.expire(window_key, window_time + 1)
    await pipe.execute()

    return False

async def _is_rate_limited(capacity: float, refill_rate: float, max_request: int,max_limit: int, window_time: int, request: Request, config: dict | None) -> bool:

    redis = request.app.state.redis

    # rateLimited = await _get_rate_limit_config(str(request.url.path), session)
    key = await _build_key(request, config)

    if config is None:
        return await _consume_token_capacity(redis, key, capacity, refill_rate, max_limit)

    else:
        return await _consume_sliding_window(redis, key, max_request, window_time) or await _consume_token_max_limit(redis, key, capacity, refill_rate, max_limit)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method
    redis = request.app.state.redis
    limited = False

    session = SessionLocal()
    try:
            # if not hasattr(request.app.state, "global_rate_limit_capacity"):
            #     cap_query = select(RateLimit.rate_limit_capacity).limit(1)
            #     ref_query = select(RateLimit.refill_rate).limit(1)
            #
            #     cap_result = await session.execute(cap_query)
            #     ref_result = await session.execute(ref_query)
            #
            #     rate_limit_capacity = cap_result.scalar_one_or_none()
            #     rate_limit_refill_rate = ref_result.scalar_one_or_none()
            #
            #     if rate_limit_capacity is not None:
            #         request.app.state.global_rate_limit_capacity = float(rate_limit_capacity)
            #     else:
            #         request.app.state.global_rate_limit_capacity = 10
            #
            #     request.app.state.global_rate_limit_refill_rate = (
            #         float(rate_limit_refill_rate) if rate_limit_refill_rate is not None else 1.0
            #     )
            #
            #
            # capacity = request.app.state.global_rate_limit_capacity
            # refill_rate = request.app.state.global_rate_limit_refill_rate
            #
            # if not hasattr(request.app.state, "rate_limit_cache"):
            #     request.app.state.rate_limit_cache = {}
            #
            # if path in request.app.state.rate_limit_cache:
            #     rateLimited = request.app.state.rate_limit_cache[path]
            # else:
            #     rateLimited = await _get_rate_limit_config(path, session)
            #     request.app.state.rate_limit_cache[path] = rateLimited

            print(f"DEBUG: Request Path: {path}")
            rateLimited = await _get_rate_limit_config(redis, path, method, session)
            print(f"DEBUG: Request Path: {path}")

            if rateLimited is None:
                capacity = 10.0
                refill_rate = 1.0
                rate_limit_max_second = 0
                window_time = 0
                max_request = 0
            else:
                capacity = rateLimited["rate_limit_capacity"]
                refill_rate = rateLimited["refill_rate"]
                rate_limit_max_second = rateLimited["max_limit_second"]
                window_time = rateLimited["window_time"]
                max_request = rateLimited["max_limit_minutes"]

            limited = await _is_rate_limited(
                capacity,
                refill_rate,
                max_request,
                rate_limit_max_second,
                window_time,
                request,
                rateLimited
            )
    except Exception as e:
        print(f"Rate limit error: {e}")
        limited = False

    finally:
        session.close()

    if limited:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": "1"},
        )

    return await call_next(request)

