"""Database-only asynchronous migration environment."""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import DatabaseSettings, database_url
from app.database import Base


def configure(connection: object) -> None:
    """Apply migrations inside the caller's schema/transaction."""
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    """Run with the configured database, without provider clients."""
    url = context.config.attributes.get("database_url")
    if url is None:
        url = database_url(DatabaseSettings().database_url.get_secret_value())
    engine = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=context.config.attributes.get("connect_args", {}),
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(configure)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Use an explicit connected database for controlled migrations")
asyncio.run(online())
