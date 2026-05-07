#!/usr/bin/env python3
"""Verify that all required services are running."""

import asyncio
import os
import sys

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "dev-secret-key-min-32-characters!!!"

import redis.asyncio as aioredis
from sqlalchemy import text

from app.core.config import settings
from app.core.database import sessionmanager


async def check_db() -> bool:
    try:
        sessionmanager.init(settings.DATABASE_URL)
        async with sessionmanager.session() as db:
            await db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f" Database: {e}")
        return False
    finally:
        await sessionmanager.close()


async def check_redis() -> bool:
    try:
        r = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await r.ping()
        await r.close()
        return True
    except Exception as e:
        print(f" Redis: {e}")
        return False


async def main():
    print("🔍 Verifying environment...\n")
    db_ok = await check_db()
    redis_ok = await check_redis()

    if db_ok and redis_ok:
        print("\n All services are healthy!")
        sys.exit(0)
    else:
        print("\n Some services are not running. Please check your Docker containers.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
