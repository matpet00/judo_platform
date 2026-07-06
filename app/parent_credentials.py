"""Generování přihlašovacích údajů rodiče."""

import re
import secrets
import string
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Parent

_USERNAME_RE = re.compile(r"[^a-z0-9]")


def _ascii_letters(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name.strip())
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return "".join(ch.lower() for ch in without_marks if ch.isalpha())


def name_part(name: str, length: int = 3) -> str:
    letters = _ascii_letters(name)
    if not letters:
        return "x" * length
    padded = (letters + "xxx")[:length]
    return padded


def build_username_base(last_name: str, first_name: str) -> str:
    return f"{name_part(last_name)}{name_part(first_name)}"


def generate_password(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def allocate_username(
    db: AsyncSession,
    first_name: str,
    last_name: str,
    *,
    exclude_parent_id: int | None = None,
) -> str:
    base = build_username_base(last_name, first_name)
    base = _USERNAME_RE.sub("", base) or "rodic"
    candidates = [base, *[f"{base}{i}" for i in range(2, 100)]]
    for candidate in candidates:
        stmt = select(Parent.id).where(Parent.username == candidate)
        if exclude_parent_id is not None:
            stmt = stmt.where(Parent.id != exclude_parent_id)
        taken = (await db.execute(stmt)).scalar_one_or_none()
        if taken is None:
            return candidate
    raise ValueError("Nepodařilo se vygenerovat volné uživatelské jméno.")
