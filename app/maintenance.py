"""Preview-first operator maintenance; no provider clients or automatic scheduler."""

import argparse
import asyncio
import json
import logging
from dataclasses import asdict

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import DatabaseSettings
from app.contracts import AppError
from app.database import Database


async def run(operation: str, *, apply: bool) -> dict[str, object]:
    """Run one bounded batch against the operator-configured database."""
    settings = DatabaseSettings()
    database = Database(settings)
    try:
        await database.ready()
        batch = await database.maintenance(settings, operation=operation, apply=apply)
        return {
            "operation": operation,
            "apply": apply,
            **asdict(batch),
            "cutoff": batch.cutoff.isoformat(),
        }
    finally:
        await database.close()


def main() -> None:
    """Expose explicit preview and apply commands with safe failure diagnostics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["reconcile", "purge"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.operation, apply=args.apply))
    except (ValidationError, SQLAlchemyError, AppError) as error:
        logging.error(
            "maintenance_failed type=%s; verify database and policy", type(error).__name__
        )
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
