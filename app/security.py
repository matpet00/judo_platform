import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Header, HTTPException, status

from app.config import settings

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

PUBLIC_WRITE_SUFFIXES = ("/verify-pin", "/parents/login")


def hash_pin(pin: str) -> str:
    return hashlib.sha256(f"{settings.pin_pepper}:{pin}".encode()).hexdigest()


def verify_pin(pin: str, pin_hash: str | None) -> bool:
    if not pin_hash:
        return False
    return secrets.compare_digest(hash_pin(pin), pin_hash)


def create_trainer_token(trainer_id: int) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_ttl_hours)
    payload = {"sub": str(trainer_id), "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires_at


def decode_trainer_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("typ") not in (None, "trainer"):
            raise ValueError("Not a trainer token.")
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trainer token.") from exc


def decode_any_token(token: str) -> tuple[str, int]:
    """Return (kind, id) for either a trainer or parent token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        kind = payload.get("typ", "trainer")
        if kind not in ("trainer", "parent"):
            raise ValueError("Unknown token type.")
        return kind, int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc


def create_parent_token(parent_id: int) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_ttl_hours)
    payload = {"sub": str(parent_id), "typ": "parent", "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires_at


def decode_parent_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("typ") != "parent":
            raise ValueError("Not a parent token.")
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid parent token.") from exc


def check_api_write_key(api_key: str | None) -> None:
    if not settings.api_write_key:
        return
    if api_key != settings.api_write_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")


def is_public_write_path(path: str) -> bool:
    return any(path.endswith(suffix) for suffix in PUBLIC_WRITE_SUFFIXES)


async def require_trainer_token(authorization: str | None = Header(default=None)) -> int:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trainer authentication is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing trainer token.")
    return decode_trainer_token(authorization.removeprefix("Bearer ").strip())


async def require_parent_token(authorization: str | None = Header(default=None)) -> int:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Parent authentication is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing parent token.")
    return decode_parent_token(authorization.removeprefix("Bearer ").strip())
