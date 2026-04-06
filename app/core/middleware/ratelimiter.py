import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.config import settings


app = FastAPI()

async def is_rate_limited(key: str, request: Request)-> bool:

    redis = request.app.state.redis
    now = time.time()

    pipe = redis.pipeline()
    pipe.get(f"token:{key}")
    pipe.get(f"last_updated:{key}")
    res = await pipe.execute()

    raw_tokens, raw_last_updated = res[0], res[1]

    if raw_tokens is not None:
        existing_tokens = float(raw_tokens)
    else:
        existing_tokens = float(settings.RATE_LIMIT_CAPACITY)

    if raw_last_updated is not None:
        last_updated = float(raw_last_updated)
    else:
        last_updated = now

    elapsed = now - last_updated
    # new_tokens = elapsed * settings.REFILL_RATE

    refilled_tokens = existing_tokens + (elapsed * settings.REFILL_RATE)
    current_tokens = min(float(settings.RATE_LIMIT_CAPACITY), refilled_tokens)

    if current_tokens >=1:
        current_tokens -= 1

        pipe = redis.pipeline()
        pipe.set(f"token:{key}", current_tokens)
        pipe.set(f"last_updated:{key}", now)
        await pipe.execute()
        return False #unblock

    return True #block

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):

    # config cho từng cái
    client_ip = request.client.host

    if await is_rate_limited(client_ip, request):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Try again later."},
            headers={"Retry-After": "1"}
        )
    response = await call_next(request)
    return response


