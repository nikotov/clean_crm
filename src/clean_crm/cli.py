from __future__ import annotations

import argparse
import time
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from .infrastructure.database import DATABASE_URL


def _project_root() -> Path:
    current_directory = Path.cwd()
    if (current_directory / "alembic.ini").exists():
        return current_directory
    return Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    project_root = _project_root()
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


def _wait_for_database(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        for attempt in range(1, max_attempts + 1):
            try:
                with engine.connect() as connection:
                    connection.execute(text("select 1"))
                return
            except Exception:
                if attempt == max_attempts:
                    raise
                time.sleep(delay_seconds)
    finally:
        engine.dispose()


def migrate() -> None:
    _wait_for_database()
    command.upgrade(_alembic_config(), "head")


def downgrade(revision: str) -> None:
    command.downgrade(_alembic_config(), revision)


def serve() -> None:
    migrate()
    uvicorn.run("clean_crm.main:app", host="0.0.0.0", port=8000, reload=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clean-crm")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("migrate", help="Apply Alembic migrations")

    downgrade_parser = subcommands.add_parser("downgrade", help="Downgrade Alembic migrations")
    downgrade_parser.add_argument("revision", help="Target revision, e.g. -1 or base")

    subcommands.add_parser("serve", help="Run migrations and start the web app")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
    elif args.command == "downgrade":
        downgrade(args.revision)
    elif args.command == "serve":
        serve()


if __name__ == "__main__":
    main()