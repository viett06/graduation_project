# app/crawler/base.py

import hashlib
import httpx
import logging
import random
import asyncio

from sqlalchemy.orm import Session
from app.core.redis import redis_config

logger = logging.getLogger(__name__)


class BaseCrawler:

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0",
    ]

    def __init__(self, bank_code: str, db: Session):
        self.bank_code = bank_code
        self.db = db

    def random_headers(self):
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept-Language": "vi,en-US;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
            "Connection": "keep-alive",
        }

    async def check_etag_changed(self, url):
        try:
            redis = redis_config.redis_client

            old_etag = await redis.get(f"etag:{self.bank_code}")

            headers = self.random_headers()

            if old_etag:
                headers["If-None-Match"] = old_etag

            async with httpx.AsyncClient() as client:
                resp = await client.head(url, headers=headers, timeout=10)

            if resp.status_code == 304:
                return False, None

            new_etag = resp.headers.get("ETag")

            if new_etag:
                await redis.setex(
                    f"etag:{self.bank_code}",
                    86400,
                    new_etag
                )

            return True, new_etag

        except Exception as e:
            logger.warning(f"[{self.bank_code}] etag fail {e}")
            return True, None

    async def check_content_hash_changed(self, content):
        try:
            redis = redis_config.redis_client

            new_hash = hashlib.md5(content.encode()).hexdigest()

            old_hash = await redis.get(f"hash:{self.bank_code}")

            if old_hash == new_hash:
                return False

            await redis.setex(
                f"hash:{self.bank_code}",
                86400,
                new_hash
            )

            return True

        except Exception as e:
            logger.warning(f"[{self.bank_code}] hash fail {e}")
            return True

    async def fetch_html(self, url, headers=None):

        headers = headers or self.random_headers()

        try:
            await asyncio.sleep(random.uniform(1.5, 4))

            async with httpx.AsyncClient(
                headers=headers,
                follow_redirects=True
            ) as client:

                resp = await client.get(url, timeout=25)
                resp.raise_for_status()

                return resp.text

        except Exception as e:
            logger.error(f"[{self.bank_code}] fetch html fail {e}")
            return None

    async def fetch_json(self, url, headers=None):

        headers = headers or self.random_headers()

        try:
            await asyncio.sleep(random.uniform(1, 3))

            async with httpx.AsyncClient(headers=headers) as client:

                resp = await client.get(url, timeout=20)
                resp.raise_for_status()

                return resp.json()

        except Exception as e:
            logger.error(f"[{self.bank_code}] fetch json fail {e}")
            return None

    def parse_rates(self, raw):
        raise NotImplementedError