import hashlib
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Header, HTTPException, Request, status

from app.config import settings

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

PUBLIC_WRITE_SUFFIXES = ("/verify-pin", "/parents/login", "/register", "/admin/login")

@dataclass(frozen=True)
class RateLimitPolicy:
    max_attempts: int
    window_seconds: int = 300
    count_every_request: bool = False


RATE_POLICIES: dict[str, RateLimitPolicy] = {
    "trainer_pin": RateLimitPolicy(max_attempts=10),
    "parent_login": RateLimitPolicy(max_attempts=10),
    "admin_login": RateLimitPolicy(max_attempts=10),
    "register_submit": RateLimitPolicy(max_attempts=5, window_seconds=3600, count_every_request=True),
    "register_lookup": RateLimitPolicy(max_attempts=40, window_seconds=300, count_every_request=True),
}

_failed_attempts: dict[str, list[float]] = defaultdict(list)

_password_hasher = PasswordHasher()


def _peppered(value: str) -> str:
    return f"{settings.pin_pepper}:{value}"


def _hash_sha256_legacy(value: str) -> str:
    return hashlib.sha256(_peppered(value).encode()).hexdigest()


def hash_pin(pin: str) -> str:
    return _password_hasher.hash(_peppered(pin))


def verify_pin(pin: str, pin_hash: str | None) -> bool:
    if not pin_hash:
        return False
    if pin_hash.startswith("$argon2"):
        try:
            _password_hasher.verify(pin_hash, _peppered(pin))
            return True
        except VerifyMismatchError:
            return False
    return secrets.compare_digest(_hash_sha256_legacy(pin), pin_hash)


def needs_rehash(pin_hash: str | None) -> bool:
    if not pin_hash or not pin_hash.startswith("$argon2"):
        return True
    return _password_hasher.check_needs_rehash(pin_hash)


def _rate_limit_key(scope: str, identifier: str) -> str:
    return f"{scope}:{identifier}"


def _policy_for(scope: str) -> RateLimitPolicy:
    return RATE_POLICIES.get(scope, RateLimitPolicy(max_attempts=10))


def _prune_attempts(key: str, window_seconds: int) -> list[float]:
    now = monotonic()
    attempts = [t for t in _failed_attempts[key] if now - t < window_seconds]
    _failed_attempts[key] = attempts
    return attempts


def check_rate_limit(scope: str, identifier: str) -> None:
    policy = _policy_for(scope)
    key = _rate_limit_key(scope, identifier)
    attempts = _prune_attempts(key, policy.window_seconds)
    if len(attempts) >= policy.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Příliš mnoho pokusů. Zkus to znovu za chvíli.",
        )
    if policy.count_every_request:
        _failed_attempts[key].append(monotonic())


def record_failed_attempt(scope: str, identifier: str) -> None:
    _failed_attempts[_rate_limit_key(scope, identifier)].append(monotonic())


def clear_rate_limit(scope: str, identifier: str) -> None:
    _failed_attempts.pop(_rate_limit_key(scope, identifier), None)


def clear_all_rate_limits() -> None:
    _failed_attempts.clear()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


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


def create_admin_token() -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_ttl_hours)
    payload = {"sub": "admin", "typ": "admin", "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires_at


def decode_admin_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("typ") != "admin":
            raise ValueError("Not an admin token.")
        return True
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token.") from exc


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
    if api_key is None or not secrets.compare_digest(api_key, settings.api_write_key):
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


@dataclass(frozen=True)
class Actor:
    kind: str  # "trainer" | "parent"
    trainer_id: int | None = None
    parent_id: int | None = None


async def get_actor(authorization: str | None = Header(default=None)) -> Actor:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token.")
    kind, subject_id = decode_any_token(authorization.removeprefix("Bearer ").strip())
    if kind == "trainer":
        return Actor(kind="trainer", trainer_id=subject_id)
    return Actor(kind="parent", parent_id=subject_id)


async def require_admin(authorization: str | None = Header(default=None)) -> bool:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin token.")
    return decode_admin_token(authorization.removeprefix("Bearer ").strip())


async def require_trainer_or_admin(authorization: str | None = Header(default=None)) -> int | None:
    """Accept a trainer token (returns trainer id) or an admin token (returns None)."""
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    if payload.get("typ") == "admin":
        return None
    return decode_trainer_token(token)


async def require_parent_token(authorization: str | None = Header(default=None)) -> int:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Parent authentication is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing parent token.")
    return decode_parent_token(authorization.removeprefix("Bearer ").strip())
