"""Isolated PostgreSQL fixtures; never reset an existing database."""

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import DatabaseSettings, database_url
from app.database import Database


def pytest_addoption(parser: pytest.Parser) -> None:
    """Opt into a disposable local test server rather than start one implicitly."""
    parser.addoption("--local-postgres", action="store_true")


@pytest.fixture(scope="session")
def postgres_url(request: pytest.FixtureRequest):
    """Use explicitly isolated TEST_DATABASE_URL or an opt-in unique local server."""
    if request.config.getoption("--local-postgres"):
        import pgserver

        with TemporaryDirectory(prefix="sarcasm-pg-") as directory:
            server = pgserver.get_server(Path(directory), cleanup_mode="stop")
            try:
                yield server.get_uri()
            finally:
                server.cleanup()
    else:
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            pytest.fail("PostgreSQL tests require isolated TEST_DATABASE_URL or --local-postgres")
        yield url


@pytest.fixture
async def db(postgres_url: str):
    """Migrate a uniquely owned schema and delete only that schema on teardown."""
    schema = "test_" + uuid4().hex
    url = database_url(postgres_url)
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    config.attributes["connect_args"] = {"options": f"-csearch_path={schema}"}
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.upgrade, config, "head")
    database = Database(DatabaseSettings(_env_file=None, database_url=postgres_url), schema=schema)
    try:
        yield database
    finally:
        await database.close()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
