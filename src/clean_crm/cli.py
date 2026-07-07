from __future__ import annotations

import argparse
import time
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from clean_crm.infrastructure.auth import create_user, delete_user, list_users, hash_password
from clean_crm.infrastructure.database import DATABASE_URL
from clean_crm.infrastructure.database import SessionLocal


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


def add_user(username: str, email: str, password: str, password_hash: str | None = None) -> None:
    with SessionLocal() as session:
        user = create_user(
            session,
            username=username,
            email=email,
            password=password,
            password_hash=password_hash,
        )
    print(f"Created user {user.id}: {user.username} <{user.email}>")


def remove_user(user_id: int | None = None, username: str | None = None) -> None:
    with SessionLocal() as session:
        user = delete_user(session, user_id=user_id, username=username)
    if user is None:
        print("No matching user found.")
        return
    print(f"Deleted user {user.id}: {user.username} <{user.email}>")

def hash_password_cli(password: str) -> None:
    hashed = hash_password(password)
    print(hashed)


def show_users() -> None:
    with SessionLocal() as session:
        users = list_users(session)

    if not users:
        print("No users found.")
        return

    for user in users:
        last_login = user.last_login.isoformat(timespec="seconds") if user.last_login else "-"
        print(f"{user.id}\t{user.username}\t{user.email}\t{last_login}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clean-crm")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("migrate", help="Apply Alembic migrations")

    downgrade_parser = subcommands.add_parser("downgrade", help="Downgrade Alembic migrations")
    downgrade_parser.add_argument("revision", help="Target revision, e.g. -1 or base")

    subcommands.add_parser("serve", help="Run migrations and start the web app")

    users_parser = subcommands.add_parser("users", help="Manage application users")
    user_subcommands = users_parser.add_subparsers(dest="user_command", required=True)

    user_subcommands.add_parser("list", help="List users")

    add_parser = user_subcommands.add_parser("add", help="Add a user")
    add_parser.add_argument("--username", required=True, help="Username for the new user")
    add_parser.add_argument("--email", required=True, help="Email for the new user")
    add_parser.add_argument("--password", required=False, help="Plain-text password for the new user")
    add_parser.add_argument("--password-hash", required=False, help="Pre-hashed password for the new user")

    remove_parser = user_subcommands.add_parser("remove", help="Remove a user")
    identity_group = remove_parser.add_mutually_exclusive_group(required=True)
    identity_group.add_argument("-username", help="Username of the user to remove")
    identity_group.add_argument("--id", type=int, help="Numeric id of the user to remove")
    hash_parser = subcommands.add_parser("hash", help="Hash a password")
    hash_parser.add_argument("--password", required=True, help="Password to hash")
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
    elif args.command == "hash":
        hash_password_cli(args.password)
    elif args.command == "users":
        if args.user_command == "list":
            show_users()
        elif args.user_command == "add":
            if not args.password and not args.password_hash:
                raise SystemExit("Either --password or --password-hash is required.")
            add_user(args.username, args.email, args.password or "", args.password_hash)
        elif args.user_command == "remove":
            remove_user(user_id=args.id, username=args.username)




if __name__ == "__main__":
    main()