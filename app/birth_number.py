"""Validace rodného čísla ve formátu RRMMDD/XXXX."""

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Student

BIRTH_NUMBER_PATTERN = re.compile(r"^\d{6}/\d{3,4}$")


def normalize_birth_number(value: str) -> str:
    return value.strip().replace(" ", "")


def validate_birth_number(value: str) -> str:
    compact = normalize_birth_number(value)
    if "/" not in compact:
        raise ValueError("Rodné číslo musí obsahovat lomítko (formát RRMMDD/XXXX).")
    if not BIRTH_NUMBER_PATTERN.fullmatch(compact):
        raise ValueError("Rodné číslo musí být ve formátu RRMMDD/XXXX.")
    return compact


def assert_unique_in_list(birth_numbers: list[str]) -> None:
    if len(set(birth_numbers)) != len(birth_numbers):
        raise HTTPException(
            status_code=400,
            detail="V jedné registraci nesmí být dvě děti se stejným rodným číslem.",
        )


async def assert_birth_numbers_available(
    db: AsyncSession,
    birth_numbers: list[str],
    *,
    exclude_student_id: int | None = None,
) -> None:
    normalized = [validate_birth_number(value) for value in birth_numbers]
    assert_unique_in_list(normalized)

    if not normalized:
        return

    query = select(Student.id, Student.birth_number).where(Student.birth_number.in_(normalized))
    if exclude_student_id is not None:
        query = query.where(Student.id != exclude_student_id)
    result = await db.execute(query)
    existing = result.first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Registraci s uvedenými údaji nelze uložit. Ověřte údaje nebo kontaktujte klub.",
        )
