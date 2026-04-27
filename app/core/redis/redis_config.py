
import redis.asyncio as aioredis
from app.core.config import settings

redis_client: aioredis.Redis = None


async def init_redis():
    global redis_client
    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6380")

    redis_client = aioredis.from_url(
        redis_url,
        decode_responses=True
    )
    await redis_client.ping()


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()