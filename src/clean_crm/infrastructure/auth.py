from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from os import environ
from secrets import token_bytes
from typing import Any

from sqlalchemy.orm import Session

from ..domain.Entities import User
from ..domain.Repositories import UserRepository
from .repositories import SQLAlchemyUserRepository


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000
AUTH_COOKIE_NAME = environ.get("CRM_AUTH_COOKIE", "clean_crm_auth")
JWT_TTL_SECONDS = int(environ.get("CRM_JWT_TTL_SECONDS", "604800"))


def _jwt_secret() -> str:
    secret = environ.get("CRM_JWT_SECRET")
    if not secret:
        raise RuntimeError("CRM_JWT_SECRET is required.")
    return secret


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt_bytes = salt or token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${_b64url_encode(salt_bytes)}${_b64url_encode(derived_key)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, key_text = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != PASSWORD_HASH_ALGORITHM:
        return False

    try:
        iterations = int(iterations_text)
        salt_bytes = _b64url_decode(salt_text)
        key_bytes = _b64url_decode(key_text)
    except (TypeError, ValueError):
        return False

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return hmac.compare_digest(derived_key, key_bytes)


def create_access_token(payload: dict[str, Any], secret: str | None = None, expires_in_seconds: int | None = None) -> str:
    signing_secret = (secret or _jwt_secret()).encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    issued_at = int(datetime.now(tz=timezone.utc).timestamp())
    token_payload = dict(payload)
    token_payload.setdefault("iat", issued_at)
    token_payload.setdefault("exp", issued_at + (expires_in_seconds or JWT_TTL_SECONDS))

    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(token_payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(signing_secret, signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


def decode_access_token(token: str, secret: str | None = None) -> dict[str, Any] | None:
    signing_secret = (secret or _jwt_secret()).encode("utf-8")
    parts = token.split(".")
    if len(parts) != 3:
        return None

    header_segment, payload_segment, signature_segment = parts
    try:
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        expected_signature = hmac.new(signing_secret, signing_input, hashlib.sha256).digest()
        provided_signature = _b64url_decode(signature_segment)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return None

        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
        if not isinstance(payload, dict):
            return None

        expires_at = payload.get("exp")
        if isinstance(expires_at, int) and int(datetime.now(tz=timezone.utc).timestamp()) >= expires_at:
            return None

        return payload
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def get_user_repository(session: Session) -> UserRepository:
    return SQLAlchemyUserRepository(session)


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user_repository = get_user_repository(session)
    user = user_repository.get_user_by_username(username)
    if user is None:
        return None

    if not verify_password(password, user.hash_password):
        return None

    user_repository.update_user_last_login(user.id, datetime.now(tz=timezone.utc).replace(tzinfo=None))
    return user


def create_user(
    session: Session,
    *,
    username: str,
    email: str,
    password: str | None = None,
    password_hash: str | None = None,
) -> User:
    if not username.strip():
        raise ValueError("Username is required.")
    if not email.strip():
        raise ValueError("Email is required.")
    if not password_hash and not password:
        raise ValueError("Either password or password_hash is required.")

    user_repository = get_user_repository(session)
    if user_repository.get_user_by_username(username) is not None:
        raise ValueError(f"User '{username}' already exists.")
    if user_repository.get_user_by_email(email) is not None:
        raise ValueError(f"Email '{email}' is already in use.")

    return user_repository.save_user(
        User(
            id=0,
            username=username,
            hash_password=password_hash or hash_password(password or ""),
            email=email,
            created_at=datetime.utcnow(),
        )
    )


def delete_user(session: Session, *, user_id: int | None = None, username: str | None = None) -> User | None:
    user_repository = get_user_repository(session)
    user: User | None
    if user_id is not None:
        user = user_repository.get_user_by_id(user_id)
    elif username is not None:
        user = user_repository.get_user_by_username(username)
    else:
        raise ValueError("User id or username is required.")

    if user is None:
        return None

    user_repository.delete_user(user.id)
    return user


def list_users(session: Session) -> list[User]:
    user_repository = get_user_repository(session)
    return user_repository.list_users()