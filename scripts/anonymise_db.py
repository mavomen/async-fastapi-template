#!/usr/bin/env python3
"""Anonymise local development database (replaces user PII)."""

import asyncio
import os
from uuid import uuid4

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "dev-secret-key-min-32-characters!!!"

from sqlalchemy import update

from app.core.config import settings
from app.core.database import sessionmanager
from app.identity.models.user import User


async def main():
    sessionmanager.init(settings.DATABASE_URL)
    async with sessionmanager.session() as db:
        # Replace all user emails and full names with anonymised values
        users = await db.execute(
            update(User).values(
                email=User.email.op("regexp_replace")(
                    User.email, r"^.*@", f"anonymised_{uuid4().hex[:8]}@"
                ),
                full_name="Anonymised User",
            )
        )
        await db.commit()
        print("Database anonymised.")

    await sessionmanager.close()


if __name__ == "__main__":
    asyncio.run(main())
